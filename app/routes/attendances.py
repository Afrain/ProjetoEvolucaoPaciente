from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import Attendance, Patient, User
from app.schemas import AttendanceCreate, AttendanceUpdate

router = APIRouter(tags=["attendances"])
templates = Jinja2Templates(directory="templates")


def validation_messages(exc: ValidationError) -> list[str]:
    return [str(error["msg"]) for error in exc.errors()]


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado.")
    return patient


def get_attendance_or_404(db: Session, attendance_id: int) -> Attendance:
    attendance = db.get(Attendance, attendance_id)
    if not attendance:
        raise HTTPException(status_code=404, detail="Atendimento nao encontrado.")
    return attendance


def attendance_context(
    request: Request,
    current_user: User,
    patient: Patient,
    attendance: Attendance | None = None,
    form_data: dict | None = None,
    errors: list[str] | None = None,
):
    return {
        "request": request,
        "current_user": current_user,
        "patient": patient,
        "attendance": attendance,
        "form_data": form_data or {},
        "errors": errors or [],
    }


@router.get("/patients/{patient_id}/attendances/new")
def new_attendance(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    patient = get_patient_or_404(db, patient_id)
    return templates.TemplateResponse(
        request,
        "attendances/form.html",
        attendance_context(request, current_user, patient),
    )


@router.post("/patients/{patient_id}/attendances")
def create_attendance(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    attendance_date: Annotated[date, Form()],
    duration_minutes: Annotated[int, Form()],
    treatment_type: Annotated[str, Form()],
    evolution_notes: Annotated[str, Form()],
):
    patient = get_patient_or_404(db, patient_id)
    form_data = {
        "attendance_date": attendance_date,
        "duration_minutes": duration_minutes,
        "treatment_type": treatment_type,
        "evolution_notes": evolution_notes,
    }
    try:
        data = AttendanceCreate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(request, current_user, patient, form_data=form_data, errors=validation_messages(exc)),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    attendance = Attendance(patient_id=patient.id, **data.model_dump())
    db.add(attendance)
    db.commit()
    return RedirectResponse(f"/patients/{patient.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/attendances/{attendance_id}/edit")
def edit_attendance(
    request: Request,
    attendance_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    attendance = get_attendance_or_404(db, attendance_id)
    return templates.TemplateResponse(
        request,
        "attendances/form.html",
        attendance_context(request, current_user, attendance.patient, attendance=attendance),
    )


@router.post("/attendances/{attendance_id}/edit")
def update_attendance(
    request: Request,
    attendance_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    attendance_date: Annotated[date, Form()],
    duration_minutes: Annotated[int, Form()],
    treatment_type: Annotated[str, Form()],
    evolution_notes: Annotated[str, Form()],
):
    attendance = get_attendance_or_404(db, attendance_id)
    form_data = {
        "attendance_date": attendance_date,
        "duration_minutes": duration_minutes,
        "treatment_type": treatment_type,
        "evolution_notes": evolution_notes,
    }
    try:
        data = AttendanceUpdate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(
                request,
                current_user,
                attendance.patient,
                attendance=attendance,
                form_data=form_data,
                errors=validation_messages(exc),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    for field, value in data.model_dump().items():
        setattr(attendance, field, value)
    db.commit()
    return RedirectResponse(f"/patients/{attendance.patient_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/attendances/{attendance_id}/delete")
def delete_attendance(
    attendance_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    attendance = get_attendance_or_404(db, attendance_id)
    patient_id = attendance.patient_id
    db.delete(attendance)
    db.commit()
    return RedirectResponse(f"/patients/{patient_id}", status_code=status.HTTP_303_SEE_OTHER)
