from datetime import date
from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
import json
import re
import unicodedata

from app.models import Patient, ProfessionalProfile, TreatmentEpisode, User


def _slug(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_") or "paciente"


def _text(value, empty: str = "—") -> str:
    return escape(str(value).strip()) if value is not None and str(value).strip() else empty


def _date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def _money(value: Decimal | None) -> str:
    if value is None:
        return "—"
    formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"


def _format_cpf_cnpj(value: str | None) -> str:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) == 11:
        return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}"
    if len(digits) == 14:
        return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"
    return _text(value)


def generate_contract_pdf(
    patient: Patient,
    episode: TreatmentEpisode,
    professional_profile: ProfessionalProfile,
    current_user: User,
) -> BytesIO:
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ModuleNotFoundError as exc:
        raise RuntimeError("Dependência ausente para gerar PDF. Instale reportlab.") from exc

    regular_font, bold_font = "Helvetica", "Helvetica-Bold"
    font_candidates = [
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
        (Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"), Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf")),
    ]
    for regular_path, bold_path in font_candidates:
        if regular_path.exists() and bold_path.exists():
            pdfmetrics.registerFont(TTFont("ContractArial", str(regular_path)))
            pdfmetrics.registerFont(TTFont("ContractArial-Bold", str(bold_path)))
            regular_font, bold_font = "ContractArial", "ContractArial-Bold"
            break

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=17 * mm,
        bottomMargin=17 * mm,
        title="Contrato de Prestação de Serviços de Fisioterapia Pós-Operatória",
        author=current_user.full_name,
    )
    blue = colors.HexColor("#4F81BD")
    light_blue = colors.HexColor("#DCE6F1")
    border = colors.HexColor("#8EA9C1")
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ContractTitle", parent=styles["Title"], fontName=bold_font, fontSize=13,
        leading=16, alignment=TA_CENTER, textColor=colors.black, spaceAfter=1.5 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ContractSubtitle", parent=title_style, fontSize=11.5, leading=14, spaceAfter=6 * mm,
    )
    heading_style = ParagraphStyle(
        "ContractHeading", parent=styles["Heading2"], fontName=bold_font, fontSize=11.5,
        leading=14, textColor=blue, spaceBefore=3.2 * mm, spaceAfter=1.8 * mm, keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ContractBody", parent=styles["BodyText"], fontName=regular_font, fontSize=11,
        leading=13.3, alignment=TA_JUSTIFY, spaceAfter=1.8 * mm,
    )
    body_bold = ParagraphStyle("ContractBodyBold", parent=body_style, fontName=bold_font)
    center_style = ParagraphStyle("ContractCenter", parent=body_style, alignment=TA_CENTER)
    small_style = ParagraphStyle("ContractSmall", parent=body_style, fontSize=10.5, leading=12.5)
    table_label_style = ParagraphStyle("TableLabel", parent=small_style, fontName=bold_font)
    table_value_style = ParagraphStyle("TableValue", parent=small_style)

    story = [
        Paragraph("CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE FISIOTERAPIA", title_style),
        Paragraph("REABILITAÇÃO PÓS-OPERATÓRIA EM CIRURGIA PLÁSTICA", subtitle_style),
        Paragraph("Pelo presente instrumento particular, de um lado:", body_style),
    ]

    def identification_table(title: str, rows: list[tuple[str, str]]):
        data = [[Paragraph(title, table_label_style), ""]]
        data.extend([[Paragraph(label, table_label_style), Paragraph(value, table_value_style)] for label, value in rows])
        table = Table(data, colWidths=[48 * mm, 124 * mm], repeatRows=1)
        table.setStyle(TableStyle([
            ("SPAN", (0, 0), (1, 0)),
            ("BACKGROUND", (0, 0), (1, 0), light_blue),
            ("TEXTCOLOR", (0, 0), (1, 0), colors.HexColor("#1F3B57")),
            ("BOX", (0, 0), (-1, -1), 0.7, border),
            ("INNERGRID", (0, 1), (-1, -1), 0.35, colors.HexColor("#B8C7D3")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.extend([table, Spacer(1, 3 * mm)])

    identification_table("CONTRATADO(A) / PRESTADOR(A)", [
        ("Nome", _text(current_user.full_name)),
        ("CPF/CNPJ", _format_cpf_cnpj(professional_profile.cpf_cnpj)),
        ("CREFITO nº", _text(professional_profile.crefito)),
        ("Endereço profissional", _text(professional_profile.professional_address)),
        ("Telefone/WhatsApp", "—"),
        ("E-mail", _text(professional_profile.professional_email)),
    ])
    identification_table("CONTRATANTE / PACIENTE", [
        ("Nome completo", _text(patient.name)),
        ("CPF", _text(patient.cpf)),
        ("RG", _text(patient.rg)),
        ("Data de nascimento", _date(patient.birth_date)),
        ("Endereço", _text(patient.address)),
        ("Telefone/WhatsApp", _text(patient.phone)),
        ("E-mail", _text(patient.email)),
    ])
    if patient.legal_guardian_name:
        identification_table("RESPONSÁVEL LEGAL, QUANDO APLICÁVEL", [
            ("Nome", _text(patient.legal_guardian_name)),
            ("CPF", _text(patient.legal_guardian_cpf)),
            ("Parentesco/qualificação", _text(patient.legal_guardian_relationship)),
        ])

    story.append(Paragraph(
        "As partes celebram o presente Contrato de Prestação de Serviços de Fisioterapia, mediante as cláusulas seguintes.",
        body_style,
    ))

    def clause(title: str, items: list[str]):
        story.append(Paragraph(title, heading_style))
        story.extend(Paragraph(item, body_style) for item in items)

    surgery = episode.surgery
    surgery_name = _text(surgery.surgery_type.name) if surgery else "Não vinculada"
    surgery_date = _date(surgery.surgery_date) if surgery else "—"
    surgeon = _text(surgery.surgeon.name) if surgery else "—"
    planned = str(surgery.planned_attendances) if surgery else "—"
    clause("1. DO OBJETO", [
        "<b>1.1.</b> O presente contrato tem por objeto a prestação de serviços profissionais de Fisioterapia voltados à avaliação, acompanhamento e reabilitação do CONTRATANTE durante o período pós-operatório de cirurgia plástica.",
        "<b>1.2.</b> O tratamento será estabelecido a partir de avaliação fisioterapêutica individual, levando em consideração as condições clínicas apresentadas pelo CONTRATANTE, o procedimento cirúrgico realizado, a evolução pós-operatória e, quando pertinente, informações e orientações fornecidas pela equipe médica responsável.",
        "<b>1.3.</b> Poderão ser utilizados procedimentos, recursos e técnicas fisioterapêuticas tecnicamente indicados pelo profissional e permitidos pelas normas profissionais aplicáveis, de acordo com a necessidade individual do paciente.",
        f"<b>Cirurgia realizada:</b> {surgery_name}<br/><b>Data da cirurgia:</b> {surgery_date}<br/><b>Cirurgião responsável, se informado:</b> {surgeon}<br/><b>Procedimento contratado / plano inicial:</b> {_text(episode.contracted_procedure)}",
    ])
    clause("2. DA AVALIAÇÃO E DO PLANO TERAPÊUTICO", [
        "<b>2.1.</b> O número, frequência e duração das sessões poderão ser ajustados conforme a avaliação fisioterapêutica e a evolução clínica do CONTRATANTE.",
        "<b>2.2.</b> O plano terapêutico poderá ser modificado durante o tratamento sempre que houver justificativa clínica, devendo o paciente ser devidamente orientado.",
        "<b>2.3.</b> Caso sejam identificados sinais, sintomas ou circunstâncias que exijam avaliação médica ou atendimento de urgência, o CONTRATADO poderá suspender ou adiar o atendimento e orientar o CONTRATANTE a procurar seu cirurgião, médico assistente ou serviço de saúde apropriado.",
    ])
    service_checks = "<br/>".join([
        f"{'[X]' if episode.service_type == 'Avulso' else '[ ]'} Sessões avulsas",
        f"{'[X]' if episode.service_type == 'Pacote' else '[ ]'} Pacote de {planned} sessões",
        f"{'[X]' if episode.service_type == 'Outro' else '[ ]'} Outro",
    ])
    payment_checks = " &nbsp;&nbsp; ".join(
        f"{'[X]' if episode.payment_method == option else '[ ]'} {option}"
        for option in ["Dinheiro", "Pix", "Cartão de débito", "Cartão de crédito", "Transferência bancária", "Outro"]
    )
    payment_terms = "À vista"
    installment_schedule = ""
    if episode.payment_condition == "Parcelado":
        payment_terms = f"Parcelado em {_text(episode.installment_count)} parcelas"
        try:
            due_dates = json.loads(episode.installment_due_dates or "[]")
        except (json.JSONDecodeError, TypeError):
            due_dates = []
        formatted_dates = []
        for index, due_date in enumerate(due_dates, start=1):
            try:
                formatted = date.fromisoformat(due_date).strftime("%d/%m/%Y")
            except (TypeError, ValueError):
                formatted = _text(due_date)
            formatted_dates.append(f"{index}ª: {formatted}")
        installment_schedule = "<br/><b>Vencimentos:</b> " + " &nbsp;&nbsp; ".join(formatted_dates)
    clause("3. DO NÚMERO DE SESSÕES E VALORES", [
        service_checks,
        f"<b>Quantidade inicialmente prevista:</b> {planned}<br/><b>Valor de cada sessão:</b> {_money(episode.session_value)}<br/><b>Valor total do pacote, quando aplicável:</b> {_money(episode.package_value)}<br/><b>Forma de pagamento:</b> {payment_checks}<br/><b>Condição de pagamento:</b> {payment_terms}.{installment_schedule}",
        "<b>3.1.</b> Serviços, procedimentos ou sessões adicionais que não estejam incluídos no plano originalmente contratado serão previamente informados e somente realizados mediante concordância do CONTRATANTE.",
        "<b>3.2.</b> Havendo contratação de pacote, as sessões efetivamente realizadas serão consideradas consumidas para todos os efeitos.",
    ])
    clause("4. DA POLÍTICA DE CANCELAMENTO E REMARCAÇÃO", [
        "<b>4.1.</b> O horário agendado é reservado exclusivamente ao CONTRATANTE.",
        "<b>4.2.</b> Qualquer cancelamento ou pedido de remarcação deverá ser comunicado ao CONTRATADO com antecedência mínima de 2 (duas) horas em relação ao horário marcado.",
        "<b>4.3.</b> O cancelamento realizado com antecedência mínima de 2 (duas) horas permitirá a remarcação do atendimento, sujeita à disponibilidade de agenda.",
        "<b>4.4.</b> O cancelamento realizado com antecedência inferior a 2 (duas) horas, bem como o não comparecimento sem aviso dentro do prazo, acarretará a <b>COBRANÇA INTEGRAL DO VALOR DA SESSÃO AGENDADA</b>, em razão da reserva do horário.",
        "<b>4.5.</b> Em pacote previamente pago, o atendimento cancelado fora do prazo ou ao qual o CONTRATANTE não comparecer será considerado como sessão utilizada.",
        "<b>4.6.</b> Situações comprovadas de caso fortuito, força maior ou emergência serão analisadas individualmente, observadas as normas legais aplicáveis.",
        "<b>4.7.</b> Caso o cancelamento seja realizado pelo CONTRATADO, nenhum valor será cobrado pela sessão não realizada, sendo oferecida a possibilidade de remarcação.",
    ])
    cancellation = Table([[Paragraph("CIÊNCIA ESPECÍFICA DA POLÍTICA DE CANCELAMENTO", body_bold)], [Paragraph(
        "Declaro que li e estou ciente da exigência de aviso mínimo de 2 horas e da cobrança integral em caso de descumprimento.<br/><br/>Rubrica do CONTRATANTE: _______________________________________",
        body_style,
    )]], colWidths=[172 * mm])
    cancellation.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.8, blue), ("BACKGROUND", (0, 0), (-1, 0), light_blue), ("PADDING", (0, 0), (-1, -1), 7)]))
    story.append(KeepTogether(cancellation))

    clauses = [
        ("5. DOS ATRASOS", [
            "<b>5.1.</b> Recomenda-se que o CONTRATANTE compareça no horário previamente agendado.",
            "<b>5.2.</b> O atraso poderá reduzir proporcionalmente o tempo disponível, sem obrigatoriedade de prolongamento da sessão.",
            "<b>5.3.</b> A redução do tempo causada pelo atraso não implicará redução automática do valor da sessão.",
            "<b>5.4.</b> Caso o atraso inviabilize a realização segura do atendimento, poderá ser aplicada a política da Cláusula 4.",
        ]),
        ("6. DAS OBRIGAÇÕES DO CONTRATADO", [
            "a) prestar os serviços com diligência, técnica, ética e dentro das atribuições profissionais do fisioterapeuta;<br/>b) realizar avaliação fisioterapêutica e registrar informações relevantes à assistência;<br/>c) informar ao CONTRATANTE as características gerais do tratamento proposto;<br/>d) respeitar a privacidade, dignidade e autonomia do CONTRATANTE;<br/>e) manter sigilo, ressalvadas as hipóteses legais;<br/>f) manter prontuário conforme a regulamentação profissional;<br/>g) recomendar avaliação complementar quando a situação ultrapassar sua competência.",
        ]),
        ("7. DAS OBRIGAÇÕES DO CONTRATANTE", [
            "a) fornecer informações completas e verdadeiras sobre sua saúde, cirurgia, intercorrências, alergias e medicamentos;<br/>b) informar alterações em seu estado de saúde;<br/>c) comunicar intercorrências pós-operatórias;<br/>d) seguir as orientações fisioterapêuticas;<br/>e) comparecer nos horários agendados;<br/>f) comunicar cancelamentos conforme a Cláusula 4;<br/>g) realizar os pagamentos acordados;<br/>h) comunicar recomendações ou restrições emitidas por outros profissionais.",
        ]),
        ("8. DOS RESULTADOS E DA NATUREZA DO SERVIÇO", [
            "<b>8.1.</b> O CONTRATANTE declara estar ciente de que não é possível garantir resultado estético, funcional ou clínico específico.",
            "<b>8.2.</b> A evolução pode variar em função de fatores individuais, tipo e extensão da cirurgia, cicatrização, saúde, intercorrências e adesão às orientações.",
            "<b>8.3.</b> Fotografias, relatos ou resultados de outros pacientes não constituem promessa de resultado idêntico.",
        ]),
        ("9. DA RESPONSABILIDADE PROFISSIONAL", [
            "<b>9.1.</b> O CONTRATADO responderá pela prestação do serviço na forma da legislação e das normas profissionais aplicáveis.",
            "<b>9.2.</b> O CONTRATADO não poderá ser responsabilizado exclusivamente pela ausência de determinado resultado quando tiver atuado dentro das normas técnicas e éticas e o resultado decorrer de fatores individuais, evolução natural, descumprimento de orientações, omissão de informações ou intercorrências não causadas pelo serviço.",
            "<b>9.3.</b> Nenhuma disposição exclui ou reduz responsabilidade que legalmente não possa ser afastada.",
        ]),
        ("10. DA CONFIDENCIALIDADE E DO SIGILO PROFISSIONAL", [
            "<b>10.1.</b> As informações clínicas e pessoais serão tratadas de maneira confidencial.<br/><b>10.2.</b> Informações somente serão divulgadas nas hipóteses autorizadas ou exigidas pela legislação.<br/><b>10.3.</b> O sigilo permanece aplicável após o encerramento deste contrato.",
        ]),
        ("11. DA PROTEÇÃO DE DADOS PESSOAIS - LGPD", [
            "<b>11.1.</b> Para os atendimentos poderão ser tratados dados pessoais e dados sensíveis de saúde.<br/><b>11.2.</b> Os dados serão utilizados para assistência, prontuário, agendamentos, cobranças, obrigações legais e exercício de direitos.<br/><b>11.3.</b> Os dados serão armazenados com medidas razoáveis de segurança pelo período necessário.<br/><b>11.4.</b> Finalidades distintas dependerão de autorização quando exigida.<br/><b>11.5.</b> O consentimento para publicidade ou redes sociais não é requisito para o tratamento fisioterapêutico.",
        ]),
        ("12. DO PRONTUÁRIO E DOS REGISTROS FISIOTERAPÊUTICOS", [
            "<b>12.1.</b> O CONTRATADO manterá registro dos atendimentos conforme a regulamentação.<br/><b>12.2.</b> O CONTRATANTE poderá solicitar acesso ao prontuário, observadas as regras aplicáveis.<br/><b>12.3.</b> Fotografias clínicas poderão integrar o prontuário, sem implicar autorização para divulgação pública.",
        ]),
        ("13. DA COMUNICAÇÃO COM OUTROS PROFISSIONAIS DE SAÚDE", [
            "<b>13.1.</b> Quando necessário à segurança assistencial, o CONTRATADO poderá recomendar contato com o cirurgião ou outro profissional.<br/><b>13.2.</b> O compartilhamento de informações observará a legislação, as necessidades assistenciais e o sigilo profissional.",
        ]),
        ("14. DA SUSPENSÃO DO ATENDIMENTO", [
            "<b>14.1.</b> O CONTRATADO poderá suspender procedimento que represente risco, não possua indicação ou dependa de avaliação adicional.<br/><b>14.2.</b> A suspensão clínica deverá ser registrada e acompanhada de orientação quando cabível.",
        ]),
        ("15. DA RESCISÃO", [
            "<b>15.1.</b> O contrato poderá ser encerrado por qualquer parte, respeitados os serviços realizados, valores devidos e a legislação.<br/><b>15.2.</b> A restituição de sessões futuras observará serviços utilizados, descontos legítimos, despesas permitidas e o Código de Defesa do Consumidor.<br/><b>15.3.</b> O CONTRATADO poderá interromper os serviços em caso de descumprimento reiterado, comportamento ofensivo, falta de pagamento, perda de segurança técnica ou quebra de confiança, mediante comunicação e respeito aos deveres éticos.<br/><b>15.4.</b> Havendo necessidade de continuidade assistencial, o paciente será adequadamente orientado.",
        ]),
        ("16. DO CASO FORTUITO E DA FORÇA MAIOR", [
            "<b>16.1.</b> Nenhuma parte será considerada inadimplente quando o cumprimento for impedido por evento imprevisível ou inevitável juridicamente caracterizado.<br/><b>16.2.</b> As partes buscarão prioritariamente a remarcação quando o atendimento for temporariamente impedido.",
        ]),
        ("17. DAS COMUNICAÇÕES E AGENDAMENTOS", [
            f"<b>WhatsApp/Telefone:</b> {_text(patient.phone)}<br/><b>E-mail:</b> {_text(patient.email)}<br/><b>17.1.</b> O CONTRATANTE compromete-se a manter seus dados de contato atualizados.",
        ]),
    ]
    for title, items in clauses:
        clause(title, items)

    story.append(Paragraph("18. TERMO DESTACADO DE CONSENTIMENTO PARA USO DE IMAGEM, VÍDEO, ÁUDIO E DEPOIMENTO", ParagraphStyle("ConsentTitle", parent=heading_style, alignment=TA_CENTER)))
    warning = Table([[Paragraph("ATENÇÃO: esta autorização é FACULTATIVA e independente da contratação dos serviços de fisioterapia.", body_bold)], [Paragraph(
        "A recusa não impedirá, limitará ou prejudicará o atendimento fisioterapêutico. Fotografias, vídeos, voz ou depoimentos somente poderão ser utilizados para divulgação mediante autorização.", body_style,
    )]], colWidths=[172 * mm])
    warning.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, blue), ("BACKGROUND", (0, 0), (-1, 0), light_blue), ("PADDING", (0, 0), (-1, -1), 7)]))
    story.append(warning)
    clause("18.1. ESCOLHA DO PACIENTE", [
        "<b>Marque apenas uma opção:</b>",
        "[ ] AUTORIZO - Autorizo, de forma livre, informada e expressa, o uso de minha imagem, vídeo, voz e/ou depoimento obtidos durante o acompanhamento fisioterapêutico para divulgação profissional do CONTRATADO.",
        "[ ] NÃO AUTORIZO - Não autorizo a utilização ou divulgação pública da minha imagem, vídeo, voz ou depoimento.",
    ])
    clause("18.2. EM CASO DE AUTORIZAÇÃO", [
        "<b>Meios autorizados:</b><br/>[ ] Instagram &nbsp;&nbsp; [ ] Facebook &nbsp;&nbsp; [ ] TikTok &nbsp;&nbsp; [ ] Site profissional<br/>[ ] WhatsApp profissional &nbsp;&nbsp; [ ] Materiais institucionais<br/>[ ] Palestras e apresentações profissionais &nbsp;&nbsp; [ ] Outros: __________________________",
        "<b>Finalidades autorizadas:</b><br/>[ ] Divulgação profissional dos serviços &nbsp;&nbsp; [ ] Conteúdo educativo<br/>[ ] Demonstração de evolução &nbsp;&nbsp; [ ] Comparação antes/depois<br/>[ ] Depoimento do paciente &nbsp;&nbsp; [ ] Finalidade acadêmica/científica<br/>[ ] Outras: _____________________________________________",
    ])
    clause("18.3. IDENTIFICAÇÃO", [
        "[ ] Autorizo que meu primeiro nome seja divulgado.<br/>[ ] Autorizo minha identificação completa.<br/>[ ] NÃO autorizo a divulgação do meu nome ou de informação que permita minha identificação, além da imagem expressamente autorizada.",
        "<b>18.4.</b> A autorização é gratuita, salvo outro ajuste escrito.<br/><b>18.5.</b> As imagens não poderão ser adulteradas ou utilizadas de forma ofensiva, enganosa, discriminatória ou descontextualizada.<br/><b>18.6.</b> O CONTRATANTE reconhece que publicações na internet podem ser copiadas por terceiros.<br/><b>18.7.</b> A autorização poderá ser revogada para utilizações futuras mediante solicitação escrita.<br/><b>18.8.</b> Recebida a revogação, o CONTRATADO interromperá novas publicações e adotará medidas razoáveis nos canais sob seu controle.",
        "<b>Local:</b> __________________________________________ &nbsp;&nbsp; <b>Data:</b> ____/____/________<br/><br/><b>Assinatura específica relativa ao uso de imagem - CONTRATANTE / PACIENTE / RESPONSÁVEL LEGAL:</b><br/><br/>____________________________________________________________",
    ])
    clause("19. DAS DISPOSIÇÕES GERAIS", [
        "<b>19.1.</b> A tolerância quanto ao descumprimento de obrigação não implicará renúncia definitiva.<br/><b>19.2.</b> Se uma disposição for inválida, as demais permanecerão válidas.<br/><b>19.3.</b> Este contrato não substitui termos específicos de consentimento necessários a determinados procedimentos.<br/><b>19.4.</b> As partes declaram compreender as condições comerciais e administrativas.",
    ])
    clause("20. DO FORO E DOS DIREITOS DO CONSUMIDOR", [
        "<b>20.1.</b> Eventuais controvérsias deverão ser preferencialmente resolvidas de forma amigável.<br/><b>20.2.</b> Não sendo possível, serão observadas as regras legais de competência territorial e proteção do consumidor.",
    ])
    clause("21. ACEITE", [
        "<b>21.1.</b> O CONTRATANTE declara que leu este instrumento, teve oportunidade de esclarecer dúvidas e concorda com as condições estabelecidas.",
        "<b>Local:</b> __________________________________________ &nbsp;&nbsp; <b>Data:</b> ____/____/________",
    ])
    signatures = Table([
        ["________________________________________", "________________________________________"],
        ["CONTRATANTE / PACIENTE", "CONTRATADO(A) / FISIOTERAPEUTA"],
        [f"Nome: {_text(patient.name)}", f"Nome: {_text(current_user.full_name)}"],
        [f"CPF: {_text(patient.cpf)}", f"CREFITO: {_text(professional_profile.crefito)}"],
    ], colWidths=[86 * mm, 86 * mm])
    signatures.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("FONTNAME", (0, 0), (-1, -1), regular_font), ("FONTNAME", (0, 1), (-1, 1), bold_font), ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("TOPPADDING", (0, 0), (-1, -1), 4)]))
    story.extend([Spacer(1, 11 * mm), signatures, PageBreak()])

    story.append(Paragraph("ANEXO - RESUMO DAS CLÁUSULAS ADICIONAIS E SUA FINALIDADE", ParagraphStyle("AnnexTitle", parent=title_style, fontSize=11)))
    annex = [
        "1. Objeto e plano terapêutico individualizado - delimita o escopo e registra que a conduta depende da avaliação e evolução clínica.",
        "2. Condições de pagamento e sessões adicionais - reduz conflitos sobre valores, pacotes, pagamentos e serviços não previstos.",
        "3. Obrigações do paciente - registra o dever de informar, comunicar intercorrências, cumprir orientações e respeitar agendamentos.",
        "4. Ausência de garantia de resultado específico - esclarece que resultados variam conforme fatores biológicos, cirúrgicos e adesão.",
        "5. Responsabilidade profissional equilibrada - preserva a responsabilidade legal e distingue fatores alheios à atuação profissional.",
        "6. Sigilo, LGPD e prontuário - protege dados pessoais e diferencia fotografia clínica de autorização para divulgação.",
        "7. Suspensão por risco clínico e encaminhamento - prioriza a segurança quando houver risco ou necessidade de avaliação médica.",
        "8. Rescisão - define encerramento, serviços realizados, valores devidos e eventual saldo de pacote.",
        "9. Caso fortuito e força maior - prevê tratamento de situações imprevisíveis que impeçam o atendimento.",
        "10. Atrasos e reserva de agenda - complementa a regra de cancelamento e protege a organização da agenda.",
    ]
    story.extend(Paragraph(item, body_style) for item in annex)
    story.append(Paragraph(
        "<b>Observação jurídica:</b> Este documento é um modelo contratual geral e deve ser adaptado à realidade do profissional ou da clínica. Recomenda-se revisão jurídica individualizada antes da adoção definitiva em operação recorrente.",
        body_style,
    ))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular_font, 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(LETTER[0] / 2, 9 * mm, f"Página {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    buffer.seek(0)
    return buffer
