from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.auth import get_current_user
from app.database import get_db
from app.models import Patient, User

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/")
def dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    patients = (
        db.query(Patient)
        .options(selectinload(Patient.attendances))
        .order_by(Patient.name.asc())
        .all()
    )

    cards = []
    total_attendances = 0
    active_patients = 0
    for patient in patients:
        attendances = patient.attendances
        total = len(attendances)
        total_attendances += total
        if patient.status == "Em tratamento":
            active_patients += 1
        cards.append(
            {
                "patient": patient,
                "total_attendances": total,
                "last_visit": attendances[0].attendance_date if attendances else None,
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
            "active_patients": active_patients,
        },
    )
