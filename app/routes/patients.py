from io import BytesIO
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Patient, Surgery, TreatmentEpisode, User
from app.schemas import PatientCreate, PatientUpdate, validation_messages

router = APIRouter(prefix="/patients", tags=["patients"])
templates = Jinja2Templates(directory="templates")

PATIENT_FIELD_LABELS = {
    "name": "Nome",
    "birth_date": "Data de nascimento",
    "phone": "Telefone",
    "health_info": "Informacoes de saude",
}


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = (
        db.query(Patient)
        .options(
            selectinload(Patient.attendances),
            selectinload(Patient.surgeries),
            selectinload(Patient.treatment_episodes)
            .selectinload(TreatmentEpisode.surgery)
            .selectinload(Surgery.surgery_type),
            selectinload(Patient.treatment_episodes)
            .selectinload(TreatmentEpisode.surgery)
            .selectinload(Surgery.surgeon),
            selectinload(Patient.treatment_episodes).selectinload(TreatmentEpisode.attendances),
        )
        .filter(Patient.id == patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado.")
    return patient


def get_episode_for_patient_or_404(patient: Patient, episode_id: int) -> TreatmentEpisode:
    episode = next((item for item in patient.treatment_episodes if item.id == episode_id), None)
    if not episode:
        raise HTTPException(status_code=404, detail="Ciclo de tratamento nao encontrado para o paciente.")
    return episode


def format_date(value) -> str:
    return value.strftime("%d/%m/%Y") if value else "-"


def build_evolution_report_sections(patient: Patient, episode: TreatmentEpisode) -> dict:
    surgery = episode.surgery
    attendances = sorted(episode.attendances, key=lambda item: item.attendance_date)
    total_done = len(attendances)
    total_planned = surgery.planned_attendances if surgery else 0

    header_lines = [
        f"Paciente: {patient.name}",
        f"Nascimento: {format_date(patient.birth_date)}",
        f"Telefone: {patient.phone or '-'}",
    ]

    cycle_lines = [
        f"Ciclo: {episode.id}",
        f"Inicio: {format_date(episode.started_on)}",
        f"Encerramento: {format_date(episode.closed_on)}",
    ]

    surgery_lines = [
        f"Cirurgia: {surgery.surgery_type.name}" if surgery else "Cirurgia: nao vinculada",
        f"Data da cirurgia: {format_date(surgery.surgery_date)}" if surgery else "Data da cirurgia: -",
        f"Cirurgiao: {surgery.surgeon.name}" if surgery else "Cirurgiao: -",
        f"Status: {surgery.status}" if surgery else "Status: -",
        f"Sessoes: {total_done}/{total_planned}",
    ]

    attendance_blocks = []
    for idx, attendance in enumerate(attendances, start=1):
        attendance_blocks.append(
            {
                "index": idx,
                "date": format_date(attendance.attendance_date),
                "type": attendance.treatment_type,
                "location": attendance.location,
                "evolution": attendance.evolution_notes,
            }
        )

    return {
        "title": "RESUMO DE EVOLUCAO CLINICA",
        "header_lines": header_lines,
        "cycle_lines": cycle_lines,
        "surgery_lines": surgery_lines,
        "attendance_blocks": attendance_blocks,
    }


def patient_context(
    request: Request,
    current_user: User,
    form_data: dict | None = None,
    errors: list[str] | None = None,
    patient: Patient | None = None,
):
    return {
        "request": request,
        "current_user": current_user,
        "patient": patient,
        "form_data": form_data or {},
        "errors": errors or [],
    }


@router.get("/new")
def new_patient(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    return templates.TemplateResponse(
        request,
        "patients/form.html",
        patient_context(request, current_user),
    )


@router.post("")
def create_patient(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
    birth_date: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    health_info: Annotated[str, Form()] = "",
):
    form_data = {
        "name": name,
        "birth_date": birth_date,
        "phone": phone,
        "health_info": health_info,
    }
    try:
        data = PatientCreate(
            name=name,
            birth_date=birth_date,
            phone=phone,
            health_info=health_info,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "patients/form.html",
            patient_context(request, current_user, form_data, validation_messages(exc, PATIENT_FIELD_LABELS)),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    patient = Patient(**data.model_dump())
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return RedirectResponse(f"/patients/{patient.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{patient_id}")
def patient_detail(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    error: str = "",
):
    patient = get_patient_or_404(db, patient_id)
    unlinked_attendances = [
        attendance for attendance in patient.attendances if attendance.treatment_episode_id is None
    ]
    return templates.TemplateResponse(
        request,
        "patients/detail.html",
        {
            "current_user": current_user,
            "patient": patient,
            "total_attendances": len(patient.attendances),
            "total_surgeries": len(patient.surgeries),
            "total_episodes": len(patient.treatment_episodes),
            "unlinked_attendances": unlinked_attendances,
            "error": error,
        },
    )


@router.get("/{patient_id}/treatment-episodes/{episode_id}/evolution-report.pdf")
def download_evolution_report_pdf(
    patient_id: int,
    episode_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=500,
            detail="Dependencia ausente para gerar PDF. Instale reportlab no ambiente.",
        ) from exc

    patient = get_patient_or_404(db, patient_id)
    episode = get_episode_for_patient_or_404(patient, episode_id)
    sections = build_evolution_report_sections(patient, episode)
    safe_name = "".join(char if char.isalnum() else "_" for char in patient.name).strip("_") or "paciente"
    filename = f"evolucao_{safe_name}_ciclo_{episode.id}.pdf"

    # Redesign completo: visual limpo, executivo e facil de ler
    page_bg = (0.985, 0.99, 1.0)
    header_bg = (0.10, 0.24, 0.39)
    card_bg = (1.0, 1.0, 1.0)
    card_soft = (0.95, 0.97, 0.99)
    border = (0.80, 0.86, 0.92)
    text_main = (0.12, 0.16, 0.21)
    text_muted = (0.37, 0.45, 0.53)
    accent = (0.16, 0.38, 0.60)

    def set_rgb(pdf_obj, rgb_tuple, *, stroke=False):
        if stroke:
            pdf_obj.setStrokeColorRGB(*rgb_tuple)
        else:
            pdf_obj.setFillColorRGB(*rgb_tuple)

    def draw_wrapped_text(pdf_obj, text, x, y, max_width, line_h, font_name="Helvetica", font_size=10):
        pdf_obj.setFont(font_name, font_size)
        words = text.split()
        if not words:
            return y - line_h

        current = words[0]
        for word in words[1:]:
            probe = f"{current} {word}"
            if pdf_obj.stringWidth(probe, font_name, font_size) <= max_width:
                current = probe
            else:
                pdf_obj.drawString(x, y, current)
                y -= line_h
                current = word
        pdf_obj.drawString(x, y, current)
        return y - line_h

    def draw_line_block(pdf_obj, lines, x, y, width, line_h, gap=1.1, font_size=8.6):
        set_rgb(pdf_obj, text_main)
        for line in lines:
            y = draw_wrapped_text(pdf_obj, line, x, y, width, line_h, "Helvetica", font_size)
            y -= gap
        return y

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin_left = 14 * mm
    margin_top = 14 * mm
    content_width = width - (margin_left * 2)
    line_height = 4.2 * mm

    pdf.setTitle(f"Evolucao clinica - {patient.name}")
    set_rgb(pdf, page_bg)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    # Header de destaque
    header_h = 25 * mm
    set_rgb(pdf, page_bg)
    pdf.rect(0, 0, width, height, fill=1, stroke=0)
    set_rgb(pdf, header_bg)
    pdf.rect(0, height - header_h, width, header_h, fill=1, stroke=0)

    header_y = height - 8.8 * mm
    set_rgb(pdf, (1, 1, 1))
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(margin_left, header_y, "RELATORIO DE EVOLUCAO CLINICA")
    pdf.setFont("Helvetica", 8.4)
    pdf.drawString(margin_left, header_y - 4.2 * mm, f"Paciente: {patient.name}  |  Ciclo: {episode.id}")
    pdf.drawRightString(width - margin_left, header_y - 4.2 * mm, f"Gerado em: {format_date(date.today())}")

    y = height - header_h - (5 * mm)

    # Cartoes resumo
    info_gap = 3.6 * mm
    info_w = (content_width - (2 * info_gap)) / 3
    info_h = 17 * mm
    labels = [
        ("SESSOES", next((line.split(": ", 1)[1] for line in sections["surgery_lines"] if line.startswith("Sessoes:")), "-")),
        ("INICIO", next((line.split(": ", 1)[1] for line in sections["cycle_lines"] if line.startswith("Inicio:")), "-")),
        ("ENCERRAMENTO", next((line.split(": ", 1)[1] for line in sections["cycle_lines"] if line.startswith("Encerramento:")), "-")),
    ]
    for i, (label, value) in enumerate(labels):
        x = margin_left + (i * (info_w + info_gap))
        set_rgb(pdf, card_bg)
        pdf.roundRect(x, y - info_h, info_w, info_h, 4, fill=1, stroke=0)
        set_rgb(pdf, border, stroke=True)
        pdf.roundRect(x, y - info_h, info_w, info_h, 4, fill=0, stroke=1)
        set_rgb(pdf, text_muted)
        pdf.setFont("Helvetica-Bold", 7.3)
        pdf.drawString(x + 2.8 * mm, y - 4.4 * mm, label)
        set_rgb(pdf, accent)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(x + 2.8 * mm, y - 10.3 * mm, value)

    y -= info_h + (4 * mm)

    # Bloco contextual
    context_h = 24 * mm
    set_rgb(pdf, card_soft)
    pdf.roundRect(margin_left, y - context_h, content_width, context_h, 4, fill=1, stroke=0)
    set_rgb(pdf, border, stroke=True)
    pdf.roundRect(margin_left, y - context_h, content_width, context_h, 4, fill=0, stroke=1)

    left_context = sections["header_lines"] + sections["cycle_lines"][:1]
    right_context = sections["surgery_lines"][:-1]
    ctx_gap = 5 * mm
    ctx_col_w = (content_width - ctx_gap - 6 * mm) / 2
    ctx_x1 = margin_left + 3 * mm
    ctx_x2 = ctx_x1 + ctx_col_w + ctx_gap
    draw_line_block(pdf, left_context, ctx_x1, y - 4.5 * mm, ctx_col_w, 3.2 * mm, gap=0.4, font_size=7.5)
    draw_line_block(pdf, right_context, ctx_x2, y - 4.5 * mm, ctx_col_w, 3.2 * mm, gap=0.4, font_size=7.5)

    y -= context_h + (4.2 * mm)

    set_rgb(pdf, accent)
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(margin_left, y, "REGISTROS DE EVOLUCAO")
    y -= 4.8 * mm

    attendance_blocks = sections["attendance_blocks"]
    if not attendance_blocks:
        set_rgb(pdf, text_muted)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(margin_left, y, "Nenhum atendimento registrado neste ciclo.")
    else:
        # Tabela moderna: colunas claras e linhas alternadas
        table_x = margin_left
        table_w = content_width
        header_h_table = 7 * mm
        available_h = y - (10 * mm)
        row_h = min(10 * mm, max(6.4 * mm, available_h / max(1, len(attendance_blocks))))

        w_no = 11 * mm
        w_date = 20 * mm
        w_type = 32 * mm
        w_location = 26 * mm
        w_notes = table_w - (w_no + w_date + w_type + w_location)

        set_rgb(pdf, header_bg)
        pdf.roundRect(table_x, y - header_h_table, table_w, header_h_table, 3, fill=1, stroke=0)
        set_rgb(pdf, (1, 1, 1))
        pdf.setFont("Helvetica-Bold", 7.8)
        col_x = table_x + 2.2 * mm
        pdf.drawString(col_x, y - 4.6 * mm, "N")
        col_x += w_no
        pdf.drawString(col_x, y - 4.6 * mm, "DATA")
        col_x += w_date
        pdf.drawString(col_x, y - 4.6 * mm, "TIPO")
        col_x += w_type
        pdf.drawString(col_x, y - 4.6 * mm, "LOCAL")
        col_x += w_location
        pdf.drawString(col_x, y - 4.6 * mm, "EVOLUCAO")
        y -= header_h_table

        body_font = 8.0 if len(attendance_blocks) <= 10 else 7.4
        for i, block in enumerate(attendance_blocks):
            row_top = y - (i * row_h)
            if i % 2 == 0:
                set_rgb(pdf, card_bg)
            else:
                set_rgb(pdf, card_soft)
            pdf.rect(table_x, row_top - row_h, table_w, row_h, fill=1, stroke=0)
            set_rgb(pdf, border, stroke=True)
            pdf.rect(table_x, row_top - row_h, table_w, row_h, fill=0, stroke=1)

            x_no = table_x + 2.2 * mm
            x_date = x_no + w_no
            x_type = x_date + w_date
            x_loc = x_type + w_type
            x_notes = x_loc + w_location
            y_text = row_top - 3.4 * mm

            set_rgb(pdf, text_main)
            pdf.setFont("Helvetica-Bold", body_font)
            pdf.drawString(x_no, y_text, f"{block['index']:02d}")
            pdf.setFont("Helvetica", body_font)
            pdf.drawString(x_date, y_text, block["date"])
            pdf.drawString(x_type, y_text, (block["type"] or "-")[:25])
            pdf.drawString(x_loc, y_text, (block["location"] or "-")[:18])
            draw_wrapped_text(
                pdf,
                block["evolution"] or "-",
                x_notes,
                y_text,
                w_notes - (2 * mm),
                2.7 * mm,
                "Helvetica",
                body_font,
            )

    pdf.save()
    buffer.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buffer, media_type="application/pdf", headers=headers)


@router.get("/{patient_id}/treatment-episodes/{episode_id}/evolution-report.txt")
def download_evolution_report_txt_legacy(
    patient_id: int,
    episode_id: int,
    _: Annotated[User, Depends(get_current_user)],
):
    return RedirectResponse(
        f"/patients/{patient_id}/treatment-episodes/{episode_id}/evolution-report.pdf",
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
    )


@router.get("/{patient_id}/edit")
def edit_patient(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    patient = get_patient_or_404(db, patient_id)
    return templates.TemplateResponse(
        request,
        "patients/form.html",
        patient_context(request, current_user, patient=patient),
    )


@router.post("/{patient_id}/edit")
def update_patient(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
    birth_date: Annotated[str, Form()] = "",
    phone: Annotated[str, Form()] = "",
    health_info: Annotated[str, Form()] = "",
):
    patient = get_patient_or_404(db, patient_id)
    form_data = {
        "name": name,
        "birth_date": birth_date,
        "phone": phone,
        "health_info": health_info,
    }
    try:
        data = PatientUpdate(
            name=name,
            birth_date=birth_date,
            phone=phone,
            health_info=health_info,
        )
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "patients/form.html",
            patient_context(
                request,
                current_user,
                form_data,
                validation_messages(exc, PATIENT_FIELD_LABELS),
                patient,
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    for field, value in data.model_dump().items():
        setattr(patient, field, value)
    db.commit()
    return RedirectResponse(f"/patients/{patient.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{patient_id}/delete")
def delete_patient(
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    patient = get_patient_or_404(db, patient_id)
    db.delete(patient)
    db.commit()
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
