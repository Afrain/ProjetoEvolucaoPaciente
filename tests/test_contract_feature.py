from decimal import Decimal
import re

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError
from pypdf import PdfReader

from app.contract_pdf import _slug, generate_contract_pdf
from app.contract_validation import get_missing_contract_fields
from app.models import Patient, ProfessionalProfile, TreatmentEpisode, User
from app.schemas import EpisodeContractDataUpdate, PatientCreate, ProfessionalProfileUpdate


def complete_contract_data():
    patient = Patient(
        name="João da Silva",
        cpf="123.456.789-00",
        rg="12.345.678-9",
        address="Rua das Flores, 10",
        email="joao@example.com",
    )
    episode = TreatmentEpisode(
        patient_id=1,
        started_on=__import__("datetime").date(2026, 1, 10),
        service_type="Avulso",
        contracted_procedure="Fisioterapia motora e plano terapêutico individualizado.",
        session_value=Decimal("150.00"),
        payment_method="Pix",
        payment_condition="À vista",
    )
    profile = ProfessionalProfile(
        user_id=1,
        cpf_cnpj="98765432100",
        crefito="CREFITO-3/123456-F",
        professional_address="Avenida Central, 200",
        professional_email="fisio@example.com",
    )
    user = User(id=1, username="fisio", full_name="Dra. Maria Souza", hashed_password="hash")
    return patient, episode, profile, user


def test_new_registration_fields_remain_optional():
    patient = PatientCreate(name="Paciente")
    profile = ProfessionalProfileUpdate()
    episode = EpisodeContractDataUpdate()

    assert patient.cpf is None
    assert profile.cpf_cnpj is None
    assert episode.service_type is None


@pytest.mark.parametrize("cpf", ["12345678900", "123.456.789-0", "abc", "123.456.789-000"])
def test_invalid_patient_cpf_is_rejected(cpf):
    with pytest.raises(ValidationError):
        PatientCreate(name="Paciente", cpf=cpf)


@pytest.mark.parametrize("document", ["1234567890", "12.345/0001-00", "documento"])
def test_invalid_professional_document_is_rejected(document):
    with pytest.raises(ValidationError):
        ProfessionalProfileUpdate(cpf_cnpj=document)


@pytest.mark.parametrize(
    ("provided", "stored"),
    [
        ("123.456.789-00", "12345678900"),
        ("12345678900", "12345678900"),
        ("12.345.678/0001-90", "12345678000190"),
        ("12345678000190", "12345678000190"),
    ],
)
def test_professional_document_is_stored_without_mask(provided, stored):
    assert ProfessionalProfileUpdate(cpf_cnpj=provided).cpf_cnpj == stored


def test_crefito_with_only_spaces_is_normalized():
    assert ProfessionalProfileUpdate(crefito="   ").crefito is None


def test_invalid_commercial_domains_are_rejected():
    with pytest.raises(ValidationError):
        EpisodeContractDataUpdate(service_type="Mensal")
    with pytest.raises(ValidationError):
        EpisodeContractDataUpdate(session_value="0")
    with pytest.raises(ValidationError):
        EpisodeContractDataUpdate(payment_condition="Fiado")
    with pytest.raises(ValidationError):
        EpisodeContractDataUpdate(installment_count=1)


def test_cash_payment_clears_installment_fields():
    data = EpisodeContractDataUpdate(
        payment_condition="À vista",
        installment_count=10,
        installment_due_dates='["2026-01-15", "2026-02-15"]',
    )
    assert data.installment_count is None
    assert data.installment_due_dates is None


def test_installment_dates_json_is_parsed_and_validated():
    data = EpisodeContractDataUpdate(
        payment_condition="Parcelado",
        installment_count=2,
        installment_due_dates='["2026-01-31", "2026-02-28"]',
    )
    assert [item.isoformat() for item in data.installment_due_dates] == ["2026-01-31", "2026-02-28"]
    with pytest.raises(ValidationError):
        EpisodeContractDataUpdate(
            payment_condition="Parcelado",
            installment_count=2,
            installment_due_dates="datas inválidas",
        )


def test_missing_fields_are_complete_and_grouped():
    patient = Patient(name="Paciente", legal_guardian_name="Responsável")
    episode = TreatmentEpisode(patient_id=1, started_on=__import__("datetime").date(2026, 1, 1))

    missing = get_missing_contract_fields(patient, episode, None)

    assert missing == {
        "Paciente": ["CPF", "RG", "Endereço", "E-mail"],
        "Perfil profissional": ["CPF/CNPJ", "CREFITO", "Endereço profissional", "E-mail profissional"],
        "Dados comerciais": [
            "Tipo de serviço",
            "Procedimento contratado",
            "Forma de pagamento",
            "Condição de pagamento",
        ],
        "Responsável legal": ["CPF do responsável legal", "Vínculo do responsável legal"],
    }


def test_complete_contract_has_no_missing_fields():
    patient, episode, profile, _ = complete_contract_data()
    assert get_missing_contract_fields(patient, episode, profile) == {}


def test_conditional_package_value_is_reported():
    patient, episode, profile, _ = complete_contract_data()
    episode.service_type = "Pacote"
    episode.session_value = None
    episode.package_value = None

    assert get_missing_contract_fields(patient, episode, profile) == {
        "Dados comerciais": ["Valor do pacote"]
    }


def test_installments_and_due_date_are_required_only_for_installment_payment():
    patient, episode, profile, _ = complete_contract_data()
    episode.payment_condition = "Parcelado"
    episode.installment_count = None

    assert get_missing_contract_fields(patient, episode, profile) == {
        "Dados comerciais": ["Quantidade de parcelas", "Datas de vencimento das parcelas"]
    }

    episode.installment_count = 2
    episode.installment_due_dates = '["2026-01-15", "2026-02-15"]'
    assert get_missing_contract_fields(patient, episode, profile) == {}

    episode.payment_condition = "À vista"
    assert get_missing_contract_fields(patient, episode, profile) == {}


# Feature: contract-generation, Property 9: Slug seguro do nome do paciente
@given(name=st.text())
def test_slug_contains_only_safe_ascii_characters(name):
    assert re.fullmatch(r"[a-z0-9_]+", _slug(name))


# Feature: contract-generation, Properties 8 e 10: Seções obrigatórias do PDF
def test_generated_pdf_contains_required_sections(tmp_path):
    patient, episode, profile, user = complete_contract_data()
    patient.legal_guardian_name = "Ana da Silva"
    patient.legal_guardian_cpf = "111.222.333-44"
    patient.legal_guardian_relationship = "Mãe"
    buffer = generate_contract_pdf(patient, episode, profile, user)

    output = tmp_path / "contract.pdf"
    output.write_bytes(buffer.getvalue())
    reader = PdfReader(output)
    text = "\n".join(page.extract_text() or "" for page in reader.pages)

    assert buffer.getvalue().startswith(b"%PDF")
    assert "CONTRATADO(A) / PRESTADOR(A)" in text
    assert "CONTRATANTE / PACIENTE" in text
    assert "RESPONSÁVEL LEGAL, QUANDO APLICÁVEL" in text
    assert "CONSENTIMENTO PARA USO DE IMAGEM" in text
    assert "NÃO AUTORIZO" in text
    assert "Ana da Silva" in text
    assert "CIÊNCIA ESPECÍFICA DA POLÍTICA DE CANCELAMENTO" in text
    assert "21. ACEITE" in text
    assert "ANEXO - RESUMO DAS CLÁUSULAS" in text
    assert "987.654.321-00" in text
    assert 6 <= len(reader.pages) <= 10


def test_generated_pdf_describes_installment_payment(tmp_path):
    patient, episode, profile, user = complete_contract_data()
    episode.payment_condition = "Parcelado"
    episode.installment_count = 6
    episode.installment_due_dates = (
        '["2026-01-12", "2026-02-12", "2026-03-12", '
        '"2026-04-12", "2026-05-12", "2026-06-12"]'
    )
    output = tmp_path / "installment-contract.pdf"
    output.write_bytes(generate_contract_pdf(patient, episode, profile, user).getvalue())
    text = "\n".join(page.extract_text() or "" for page in PdfReader(output).pages)

    assert "Parcelado em 6 parcelas" in text
    assert "1ª: 12/01/2026" in text
    assert "6ª: 12/06/2026" in text
