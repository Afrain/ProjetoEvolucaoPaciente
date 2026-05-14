from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Patient, Surgery, TreatmentEpisode, User
from app.schemas import SURGERY_LEGACY_IN_PROGRESS_STATUS, SURGERY_IN_TREATMENT_STATUS

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/dashboard")
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    patients = (
        db.query(Patient)
        .options(
            selectinload(Patient.attendances),
            selectinload(Patient.surgeries),
            selectinload(Patient.treatment_episodes)
            .selectinload(TreatmentEpisode.surgery)
            .selectinload(Surgery.surgery_type),
            selectinload(Patient.treatment_episodes).selectinload(TreatmentEpisode.attendances),
        )
        .order_by(Patient.name.asc())
        .all()
    )

    cards = []
    total_attendances = 0
    total_surgeries = 0
    active_surgeries = 0
    for patient in patients:
        attendances = patient.attendances
        total = len(attendances)
        total_attendances += total
        total_surgeries += len(patient.surgeries)
        active_surgeries += sum(
            1
            for surgery in patient.surgeries
            if surgery.status in {SURGERY_IN_TREATMENT_STATUS, SURGERY_LEGACY_IN_PROGRESS_STATUS}
        )
        latest_episode = patient.treatment_episodes[0] if patient.treatment_episodes else None
        if latest_episode and latest_episode.surgery:
            progress_text = f"{len(latest_episode.attendances)} sessao de {latest_episode.surgery.planned_attendances}"
        else:
            progress_text = "0 sessao de 0"
        cards.append(
            {
                "patient": patient,
                "total_attendances": total,
                "last_visit": attendances[0].attendance_date if attendances else None,
                "progress_text": progress_text,
            }
        )

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "current_user": current_user,
            "patients": cards,
            "total_patients": len(patients),
            "total_attendances": total_attendances,
            "total_surgeries": total_surgeries,
            "active_surgeries": active_surgeries,
        },
    )
