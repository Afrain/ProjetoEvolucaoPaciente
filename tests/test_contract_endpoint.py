from datetime import date
from decimal import Decimal

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import get_current_user
from app.database import Base, get_db
from app.models import Patient, ProfessionalProfile, TreatmentEpisode, User
from app.routes import patients


def build_client(*, complete: bool):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as db:
        user = User(username="fisio", full_name="Fisioterapeuta Teste", hashed_password="hash")
        patient = Patient(name="José Teste")
        episode = TreatmentEpisode(patient=patient, started_on=date(2026, 1, 1))
        db.add_all([user, patient, episode])
        db.flush()
        if complete:
            patient.cpf = "123.456.789-00"
            patient.rg = "1234567"
            patient.address = "Rua Teste, 1"
            patient.email = "paciente@example.com"
            episode.service_type = "Avulso"
            episode.contracted_procedure = "Procedimento de teste"
            episode.session_value = Decimal("100.00")
            episode.payment_method = "Pix"
            episode.payment_condition = "À vista"
            db.add(
                ProfessionalProfile(
                    user_id=user.id,
                    cpf_cnpj="98765432100",
                    crefito="CREFITO-3/123",
                    professional_address="Avenida Teste, 2",
                    professional_email="fisio@example.com",
                )
            )
        db.commit()
        user_id, patient_id, episode_id = user.id, patient.id, episode.id

    app = FastAPI()
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(patients.router)

    def override_db():
        with session_factory() as db:
            yield db

    def override_user():
        with session_factory() as db:
            return db.get(User, user_id)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app), patient_id, episode_id


def test_endpoint_blocks_generation_and_lists_all_pending_fields():
    client, patient_id, episode_id = build_client(complete=False)

    response = client.get(f"/patients/{patient_id}/treatment-episodes/{episode_id}/contract.pdf")

    assert response.status_code == 422
    assert "Não foi possível gerar o contrato" in response.text
    assert "CPF/CNPJ" in response.text
    assert "Procedimento contratado" in response.text
    assert response.headers["content-type"].startswith("text/html")


def test_endpoint_returns_named_pdf_when_data_is_complete():
    client, patient_id, episode_id = build_client(complete=True)

    response = client.get(f"/patients/{patient_id}/treatment-episodes/{episode_id}/contract.pdf")

    assert response.status_code == 200
    assert response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"
    assert f'filename="contrato_jose_teste_{episode_id}.pdf"' in response.headers["content-disposition"]


def test_endpoint_rejects_episode_from_another_patient():
    client, patient_id, episode_id = build_client(complete=True)

    response = client.get(f"/patients/{patient_id + 999}/treatment-episodes/{episode_id}/contract.pdf")

    assert response.status_code == 404
