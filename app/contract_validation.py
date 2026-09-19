import json
from datetime import date

from app.models import Patient, ProfessionalProfile, TreatmentEpisode


def _is_missing(value) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()


def get_missing_contract_fields(
    patient: Patient,
    episode: TreatmentEpisode,
    professional_profile: ProfessionalProfile | None,
) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {}

    patient_fields = (
        ("cpf", "CPF"),
        ("rg", "RG"),
        ("address", "Endereço"),
        ("email", "E-mail"),
    )
    patient_missing = [label for field, label in patient_fields if _is_missing(getattr(patient, field, None))]
    if patient_missing:
        groups["Paciente"] = patient_missing

    profile_fields = (
        ("cpf_cnpj", "CPF/CNPJ"),
        ("crefito", "CREFITO"),
        ("professional_address", "Endereço profissional"),
        ("professional_email", "E-mail profissional"),
    )
    profile_missing = [
        label
        for field, label in profile_fields
        if professional_profile is None or _is_missing(getattr(professional_profile, field, None))
    ]
    if profile_missing:
        groups["Perfil profissional"] = profile_missing

    episode_fields = (
        ("service_type", "Tipo de serviço"),
        ("contracted_procedure", "Procedimento contratado"),
        ("payment_method", "Forma de pagamento"),
        ("payment_condition", "Condição de pagamento"),
    )
    commercial_missing = [label for field, label in episode_fields if _is_missing(getattr(episode, field, None))]
    if episode.service_type == "Avulso" and _is_missing(episode.session_value):
        commercial_missing.append("Valor da sessão")
    elif episode.service_type == "Pacote" and _is_missing(episode.package_value):
        commercial_missing.append("Valor do pacote")
    if episode.payment_condition == "Parcelado":
        if _is_missing(episode.installment_count):
            commercial_missing.append("Quantidade de parcelas")
        try:
            due_dates = json.loads(episode.installment_due_dates or "[]")
        except (json.JSONDecodeError, TypeError):
            due_dates = []
        expected_count = episode.installment_count or 0
        valid_due_dates = []
        for item in due_dates:
            try:
                valid_due_dates.append(date.fromisoformat(item))
            except (TypeError, ValueError):
                pass
        if expected_count and len(valid_due_dates) != expected_count:
            commercial_missing.append(f"Datas de vencimento das {expected_count} parcelas")
        elif not expected_count and not due_dates:
            commercial_missing.append("Datas de vencimento das parcelas")
    if commercial_missing:
        groups["Dados comerciais"] = commercial_missing

    if not _is_missing(patient.legal_guardian_name):
        guardian_fields = (
            ("legal_guardian_cpf", "CPF do responsável legal"),
            ("legal_guardian_relationship", "Vínculo do responsável legal"),
        )
        guardian_missing = [
            label for field, label in guardian_fields if _is_missing(getattr(patient, field, None))
        ]
        if guardian_missing:
            groups["Responsável legal"] = guardian_missing

    return groups
