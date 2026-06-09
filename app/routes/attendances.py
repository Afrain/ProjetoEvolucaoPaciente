from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, object_session

from app.auth import get_current_user
from app.database import get_db
from app.models import Attendance, Patient, TreatmentEpisode, User
from app.schemas import (
    ATTENDANCE_LOCATION_OPTIONS,
    SURGERY_IN_TREATMENT_STATUS,
    AttendanceCreate,
    EpisodeStatusUpdate,
    AttendanceUpdate,
    validation_messages,
)

router = APIRouter(tags=["attendances"])
templates = Jinja2Templates(directory="templates")

ATTENDANCE_FIELD_LABELS = {
    "treatment_episode_id": "Ciclo de tratamento",
    "attendance_date": "Data do atendimento",
    "location": "Local de atendimento",
    "treatment_type": "Tipo de tratamento",
    "evolution_notes": "Observacões de evolucão",
}


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente não encontrado.")
    return patient


def get_attendance_or_404(db: Session, attendance_id: int) -> Attendance:
    attendance = db.get(Attendance, attendance_id)
    if not attendance:
        raise HTTPException(status_code=404, detail="Atendimento não encontrado.")
    return attendance


def attendance_context(
    request: Request,
    current_user: User,
    patient: Patient,
    attendance: Attendance | None = None,
    form_data: dict | None = None,
    errors: list[str] | None = None,
    lock_episode: bool = False,
):
    treatment_episodes = db_treatment_episodes_for_context(patient)
    if attendance is None:
        treatment_episodes = [item for item in treatment_episodes if not item.surgery or item.surgery.status != "Alta"]

    return {
        "request": request,
        "current_user": current_user,
        "patient": patient,
        "attendance": attendance,
        "form_data": form_data or {},
        "errors": errors or [],
        "treatment_episodes": treatment_episodes,
        "lock_episode": lock_episode,
        "attendance_location_options": ATTENDANCE_LOCATION_OPTIONS,
    }


def db_treatment_episodes_for_context(patient: Patient) -> list[TreatmentEpisode]:
    session = object_session(patient)
    if session is None:
        return []
    return (
        session.query(TreatmentEpisode)
        .filter(TreatmentEpisode.patient_id == patient.id)
        .order_by(TreatmentEpisode.started_on.desc(), TreatmentEpisode.id.desc())
        .all()
    )


def get_episode_for_patient(db: Session, patient: Patient, treatment_episode_id: int) -> TreatmentEpisode | None:
    treatment_episode = db.get(TreatmentEpisode, treatment_episode_id)
    if not treatment_episode or treatment_episode.patient_id != patient.id:
        return None
    return treatment_episode


def count_episode_attendances(db: Session, episode: TreatmentEpisode, *, ignore_attendance_id: int | None = None) -> int:
    query = db.query(func.count(Attendance.id)).filter(Attendance.treatment_episode_id == episode.id)
    if ignore_attendance_id is not None:
        query = query.filter(Attendance.id != ignore_attendance_id)
    return int(query.scalar() or 0)


def check_episode_accepts_attendance(
    db: Session,
    episode: TreatmentEpisode,
    *,
    ignore_attendance_id: int | None = None,
) -> str | None:
    surgery = episode.surgery
    if not surgery:
        return "O ciclo selecionado não possui cirurgia vinculada."
    is_editing_existing = False
    if ignore_attendance_id is not None:
        is_editing_existing = any(item.id == ignore_attendance_id for item in episode.attendances)
    if surgery.status == "Alta" and not is_editing_existing:
        return "Esta cirurgia já recebeu alta e não aceita novos atendimentos."

    completed = count_episode_attendances(db, episode, ignore_attendance_id=ignore_attendance_id)
    if completed >= surgery.planned_attendances:
        surgery.status = "Alta"
        if episode.closed_on is None:
            episode.closed_on = date.today()
        return "Limite de atendimentos atingido para esta cirurgia."
    return None


def sync_surgery_status_from_episode(db: Session, episode: TreatmentEpisode) -> None:
    surgery = episode.surgery
    if not surgery:
        return
    completed = count_episode_attendances(db, episode)
    if completed >= surgery.planned_attendances:
        surgery.status = "Alta"
        if episode.closed_on is None:
            episode.closed_on = date.today()
    elif surgery.status == "Alta":
        surgery.status = SURGERY_IN_TREATMENT_STATUS
        episode.closed_on = None


@router.get("/patients/{patient_id}/attendances/new")
def new_attendance(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    treatment_episode_id: str = "",
):
    patient = get_patient_or_404(db, patient_id)
    lock_episode = False
    if treatment_episode_id:
        try:
            episode_id_value = int(treatment_episode_id)
        except ValueError:
            episode_id_value = 0
        episode = get_episode_for_patient(db, patient, episode_id_value) if episode_id_value else None
        if episode is None:
            raise HTTPException(status_code=404, detail="Ciclo de tratamento não encontrado para o paciente.")
        if episode.surgery and episode.surgery.status == "Alta":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este ciclo já recebeu alta.")
        block_error = check_episode_accepts_attendance(db, episode)
        if block_error:
            db.commit()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=block_error)
        lock_episode = True
    return templates.TemplateResponse(
        request,
        "attendances/form.html",
        attendance_context(
            request,
            current_user,
            patient,
            form_data=(
                {
                    "treatment_episode_id": treatment_episode_id,
                    "attendance_date": date.today().isoformat(),
                }
                if treatment_episode_id
                else {"attendance_date": date.today().isoformat()}
            ),
            lock_episode=lock_episode,
        ),
    )


@router.post("/patients/{patient_id}/attendances")
def create_attendance(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    attendance_date: Annotated[date, Form()],
    location: Annotated[str, Form()],
    treatment_type: Annotated[str, Form()],
    evolution_notes: Annotated[str, Form()],
    treatment_episode_id: Annotated[str, Form()],
):
    patient = get_patient_or_404(db, patient_id)
    form_data = {
        "attendance_date": attendance_date,
        "location": location,
        "treatment_type": treatment_type,
        "evolution_notes": evolution_notes,
        "treatment_episode_id": treatment_episode_id,
    }
    try:
        data = AttendanceCreate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(
                request,
                current_user,
                patient,
                form_data=form_data,
                errors=validation_messages(exc, ATTENDANCE_FIELD_LABELS),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    episode = get_episode_for_patient(db, patient, data.treatment_episode_id)
    if episode is None:
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(
                request,
                current_user,
                patient,
                form_data=form_data,
                errors=["Selecione um ciclo de tratamento válido."],
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    block_error = check_episode_accepts_attendance(db, episode)
    if block_error:
        db.flush()
        db.commit()
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(
                request,
                current_user,
                patient,
                form_data=form_data,
                errors=[block_error],
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    surgery = episode.surgery
    attendance = Attendance(
        patient_id=patient.id,
        treatment_episode_id=data.treatment_episode_id,
        surgeon_id=surgery.surgeon_id if surgery else None,
        attendance_date=data.attendance_date,
        location=data.location,
        treatment_type=data.treatment_type,
        evolution_notes=data.evolution_notes,
    )
    db.add(attendance)
    db.flush()
    sync_surgery_status_from_episode(db, episode)
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
    location: Annotated[str, Form()],
    treatment_type: Annotated[str, Form()],
    evolution_notes: Annotated[str, Form()],
    treatment_episode_id: Annotated[str, Form()],
):
    attendance = get_attendance_or_404(db, attendance_id)
    form_data = {
        "attendance_date": attendance_date,
        "location": location,
        "treatment_type": treatment_type,
        "evolution_notes": evolution_notes,
        "treatment_episode_id": treatment_episode_id,
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
                errors=validation_messages(exc, ATTENDANCE_FIELD_LABELS),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    target_episode = get_episode_for_patient(db, attendance.patient, data.treatment_episode_id)
    if target_episode is None:
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(
                request,
                current_user,
                attendance.patient,
                attendance=attendance,
                form_data=form_data,
                errors=["Selecione um ciclo de tratamento válido."],
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    old_episode = attendance.treatment_episode
    block_error = check_episode_accepts_attendance(db, target_episode, ignore_attendance_id=attendance.id)
    if block_error:
        db.flush()
        db.commit()
        return templates.TemplateResponse(
            request,
            "attendances/form.html",
            attendance_context(
                request,
                current_user,
                attendance.patient,
                attendance=attendance,
                form_data=form_data,
                errors=[block_error],
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    surgery = target_episode.surgery
    attendance.treatment_episode_id = data.treatment_episode_id
    attendance.surgeon_id = surgery.surgeon_id if surgery else None
    attendance.attendance_date = data.attendance_date
    attendance.location = data.location
    attendance.treatment_type = data.treatment_type
    attendance.evolution_notes = data.evolution_notes

    db.flush()
    sync_surgery_status_from_episode(db, target_episode)
    if old_episode and old_episode.id != target_episode.id:
        sync_surgery_status_from_episode(db, old_episode)
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
    episode = attendance.treatment_episode
    db.delete(attendance)
    db.flush()
    if episode:
        sync_surgery_status_from_episode(db, episode)
    db.commit()
    return RedirectResponse(f"/patients/{patient_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.patch("/treatment-episodes/{episode_id}/status")
def patch_treatment_episode_status(
    episode_id: int,
    payload: EpisodeStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    episode = db.get(TreatmentEpisode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Ciclo de tratamento não encontrado.")
    if not episode.surgery:
        raise HTTPException(status_code=400, detail="Ciclo sem cirurgia vinculada não possui status clínico.")

    episode.surgery.status = payload.status
    episode.closed_on = date.today()
    db.commit()
    return {
        "episode_id": episode.id,
        "surgery_id": episode.surgery.id,
        "status": episode.surgery.status,
        "closed_on": episode.closed_on.strftime("%d/%m/%Y"),
        "message": "Ciclo atualizado para alta com sucesso.",
    }


@router.post("/treatment-episodes/{episode_id}/mark-high")
def mark_treatment_episode_high(
    episode_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    episode = db.get(TreatmentEpisode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail="Ciclo de tratamento não encontrado.")
    if not episode.surgery:
        raise HTTPException(status_code=400, detail="Ciclo sem cirurgia vinculada não possui status clínico.")

    episode.surgery.status = "Alta"
    episode.closed_on = date.today()
    patient_id = episode.patient_id
    db.commit()
    return RedirectResponse(f"/patients/{patient_id}", status_code=status.HTTP_303_SEE_OTHER)
