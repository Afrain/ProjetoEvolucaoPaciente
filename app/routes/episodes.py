from typing import Annotated
import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import TreatmentEpisode, User
from app.schemas import (
    PAYMENT_METHOD_OPTIONS,
    PAYMENT_CONDITION_OPTIONS,
    SERVICE_TYPE_OPTIONS,
    EpisodeContractDataUpdate,
    validation_messages,
)

router = APIRouter(tags=["episodes"])
templates = Jinja2Templates(directory="templates")

CONTRACT_DATA_FIELD_LABELS = {
    "service_type": "Tipo de serviço",
    "contracted_procedure": "Procedimento contratado",
    "session_value": "Valor da sessão",
    "package_value": "Valor do pacote",
    "payment_method": "Forma de pagamento",
    "payment_condition": "Condição de pagamento",
    "installment_count": "Quantidade de parcelas",
    "installment_due_dates": "Datas de vencimento das parcelas",
}


def get_episode_or_404(db: Session, episode_id: int) -> TreatmentEpisode:
    episode = db.get(TreatmentEpisode, episode_id)
    if episode is None:
        raise HTTPException(status_code=404, detail="Ciclo de tratamento não encontrado.")
    return episode


def contract_data_context(
    request: Request,
    current_user: User,
    episode: TreatmentEpisode,
    *,
    form_data: dict | None = None,
    errors: list[str] | None = None,
) -> dict:
    try:
        installment_due_dates = json.loads(episode.installment_due_dates or "[]")
    except (json.JSONDecodeError, TypeError):
        installment_due_dates = []
    return {
        "request": request,
        "current_user": current_user,
        "episode": episode,
        "patient": episode.patient,
        "form_data": form_data or {},
        "errors": errors or [],
        "service_type_options": SERVICE_TYPE_OPTIONS,
        "payment_method_options": PAYMENT_METHOD_OPTIONS,
        "payment_condition_options": PAYMENT_CONDITION_OPTIONS,
        "is_locked": bool(episode.surgery and episode.surgery.status == "Alta"),
        "installment_due_dates": installment_due_dates,
    }


@router.get("/treatment-episodes/{episode_id}/contract-data")
def get_contract_data(
    request: Request,
    episode_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    episode = get_episode_or_404(db, episode_id)
    return templates.TemplateResponse(
        request,
        "episodes/contract_data_form.html",
        contract_data_context(request, current_user, episode),
    )


@router.post("/treatment-episodes/{episode_id}/contract-data")
def update_contract_data(
    request: Request,
    episode_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    service_type: Annotated[str, Form()] = "",
    contracted_procedure: Annotated[str, Form()] = "",
    session_value: Annotated[str, Form()] = "",
    package_value: Annotated[str, Form()] = "",
    payment_method: Annotated[str, Form()] = "",
    payment_condition: Annotated[str, Form()] = "",
    installment_count: Annotated[str, Form()] = "",
    installment_due_dates: Annotated[str, Form()] = "",
):
    episode = get_episode_or_404(db, episode_id)
    form_data = {
        "service_type": service_type,
        "contracted_procedure": contracted_procedure,
        "session_value": session_value,
        "package_value": package_value,
        "payment_method": payment_method,
        "payment_condition": payment_condition,
        "installment_count": installment_count,
        "installment_due_dates": installment_due_dates,
    }
    if episode.surgery and episode.surgery.status == "Alta":
        return templates.TemplateResponse(
            request,
            "episodes/contract_data_form.html",
            contract_data_context(
                request,
                current_user,
                episode,
                form_data=form_data,
                errors=["Os dados comerciais não podem ser alterados após a alta."],
            ),
            status_code=status.HTTP_409_CONFLICT,
        )

    try:
        data = EpisodeContractDataUpdate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "episodes/contract_data_form.html",
            contract_data_context(
                request,
                current_user,
                episode,
                form_data=form_data,
                errors=validation_messages(exc, CONTRACT_DATA_FIELD_LABELS),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    normalized_data = data.model_dump()
    due_dates = normalized_data.pop("installment_due_dates", None)
    normalized_data["installment_due_dates"] = (
        json.dumps([item.isoformat() for item in due_dates]) if due_dates else None
    )
    if data.payment_condition != "Parcelado":
        normalized_data["installment_count"] = None
        normalized_data["installment_due_dates"] = None
    for field, value in normalized_data.items():
        setattr(episode, field, value)
    db.commit()
    return RedirectResponse(f"/patients/{episode.patient_id}", status_code=status.HTTP_303_SEE_OTHER)
