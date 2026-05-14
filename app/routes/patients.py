from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
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
