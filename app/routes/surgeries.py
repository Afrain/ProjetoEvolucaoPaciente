from datetime import date
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy.orm import Session, object_session

from app.auth import get_current_user
from app.database import get_db
from app.models import Attendance, Patient, Surgeon, Surgery, SurgeryType, TreatmentEpisode, User
from app.schemas import SURGERY_STATUS_OPTIONS, SurgeryCreate, SurgeryStatusUpdate, SurgeryUpdate, validation_messages

router = APIRouter(tags=["surgeries"])
templates = Jinja2Templates(directory="templates")

SURGERY_FIELD_LABELS = {
    "surgery_date": "Data da cirurgia",
    "surgery_type_id": "Tipo de cirurgia",
    "surgeon_id": "Cirurgiao",
    "planned_attendances": "Total previsto de atendimentos",
    "status": "Status da cirurgia",
}


def get_patient_or_404(db: Session, patient_id: int) -> Patient:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Paciente nao encontrado.")
    return patient


def get_surgery_or_404(db: Session, surgery_id: int) -> Surgery:
    surgery = db.get(Surgery, surgery_id)
    if not surgery:
        raise HTTPException(status_code=404, detail="Cirurgia nao encontrada.")
    return surgery


def surgery_context(
    request: Request,
    current_user: User,
    patient: Patient,
    surgery: Surgery | None = None,
    form_data: dict | None = None,
    errors: list[str] | None = None,
):
    return {
        "request": request,
        "current_user": current_user,
        "patient": patient,
        "surgery": surgery,
        "form_data": form_data or {},
        "errors": errors or [],
        "surgery_types": db_options(patient, SurgeryType),
        "surgeons": db_options(patient, Surgeon),
        "surgery_status_options": SURGERY_STATUS_OPTIONS,
    }


def db_options(patient: Patient, model: type[SurgeryType] | type[Surgeon]):
    session = object_session(patient)
    if session is None:
        return []
    return session.query(model).order_by(model.name.asc()).all()


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


def get_or_create_named_option(db: Session, model: type[SurgeryType] | type[Surgeon], name: str):
    clean_name = normalize_name(name)
    if len(clean_name) < 2:
        raise ValueError("Informe um nome com pelo menos 2 caracteres.")

    existing = db.query(model).filter(func.lower(model.name) == clean_name.lower()).first()
    if existing:
        return existing

    option = model(name=clean_name)
    db.add(option)
    db.commit()
    db.refresh(option)
    return option


def update_named_option(db: Session, model: type[SurgeryType] | type[Surgeon], option_id: int, name: str):
    option = db.get(model, option_id)
    if not option:
        raise HTTPException(status_code=404, detail="Cadastro nao encontrado.")

    clean_name = normalize_name(name)
    if len(clean_name) < 2:
        raise ValueError("Informe um nome com pelo menos 2 caracteres.")

    existing = (
        db.query(model)
        .filter(func.lower(model.name) == clean_name.lower(), model.id != option_id)
        .first()
    )
    if existing:
        raise ValueError("Ja existe um cadastro com esse nome.")

    option.name = clean_name
    db.commit()
    return option


def redirect_to_options(**params: str) -> RedirectResponse:
    query = f"?{urlencode(params)}" if params else ""
    return RedirectResponse(f"/surgical-options{query}", status_code=status.HTTP_303_SEE_OTHER)


def wants_json(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "")


def ensure_surgery_options(db: Session, data: SurgeryCreate | SurgeryUpdate) -> list[str]:
    errors = []
    if not db.get(SurgeryType, data.surgery_type_id):
        errors.append("Selecione um tipo de cirurgia valido.")
    if not db.get(Surgeon, data.surgeon_id):
        errors.append("Selecione um cirurgiao valido.")
    return errors


@router.get("/surgical-options")
def surgical_options(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    notice: str = "",
    error: str = "",
):
    return templates.TemplateResponse(
        request,
        "surgeries/options.html",
        {
            "current_user": current_user,
            "surgery_types": db.query(SurgeryType).order_by(SurgeryType.name.asc()).all(),
            "surgeons": db.query(Surgeon).order_by(Surgeon.name.asc()).all(),
            "notice": notice,
            "error": error,
        },
    )


@router.get("/patients/{patient_id}/surgeries/new")
def new_surgery(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    patient = get_patient_or_404(db, patient_id)
    return templates.TemplateResponse(
        request,
        "surgeries/form.html",
        surgery_context(request, current_user, patient),
    )


@router.post("/patients/{patient_id}/surgeries")
def create_surgery(
    request: Request,
    patient_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    surgery_date: Annotated[date, Form()],
    surgery_type_id: Annotated[int, Form()],
    surgeon_id: Annotated[int, Form()],
    planned_attendances: Annotated[int, Form()],
    status_value: Annotated[str, Form(alias="status")] = "Em progresso",
):
    patient = get_patient_or_404(db, patient_id)
    form_data = {
        "surgery_date": surgery_date,
        "surgery_type_id": surgery_type_id,
        "surgeon_id": surgeon_id,
        "planned_attendances": planned_attendances,
        "status": status_value,
    }
    try:
        data = SurgeryCreate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "surgeries/form.html",
            surgery_context(request, current_user, patient, form_data=form_data, errors=validation_messages(exc, SURGERY_FIELD_LABELS)),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    option_errors = ensure_surgery_options(db, data)
    if option_errors:
        return templates.TemplateResponse(
            request,
            "surgeries/form.html",
            surgery_context(request, current_user, patient, form_data=form_data, errors=option_errors),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    surgery = Surgery(patient_id=patient.id, **data.model_dump())
    surgery.treatment_episode = TreatmentEpisode(patient_id=patient.id, started_on=data.surgery_date)
    db.add(surgery)
    db.commit()
    return RedirectResponse(f"/patients/{patient.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/surgeries/{surgery_id}/edit")
def edit_surgery(
    request: Request,
    surgery_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    surgery = get_surgery_or_404(db, surgery_id)
    return templates.TemplateResponse(
        request,
        "surgeries/form.html",
        surgery_context(request, current_user, surgery.patient, surgery=surgery),
    )


@router.post("/surgeries/{surgery_id}/edit")
def update_surgery(
    request: Request,
    surgery_id: int,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    surgery_date: Annotated[date, Form()],
    surgery_type_id: Annotated[int, Form()],
    surgeon_id: Annotated[int, Form()],
    planned_attendances: Annotated[int, Form()],
    status_value: Annotated[str, Form(alias="status")] = "Em progresso",
):
    surgery = get_surgery_or_404(db, surgery_id)
    form_data = {
        "surgery_date": surgery_date,
        "surgery_type_id": surgery_type_id,
        "surgeon_id": surgeon_id,
        "planned_attendances": planned_attendances,
        "status": status_value,
    }
    try:
        data = SurgeryUpdate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "surgeries/form.html",
            surgery_context(
                request,
                current_user,
                surgery.patient,
                surgery=surgery,
                form_data=form_data,
                errors=validation_messages(exc, SURGERY_FIELD_LABELS),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    option_errors = ensure_surgery_options(db, data)
    if option_errors:
        return templates.TemplateResponse(
            request,
            "surgeries/form.html",
            surgery_context(request, current_user, surgery.patient, surgery=surgery, form_data=form_data, errors=option_errors),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    completed_count = len(surgery.treatment_episode.attendances) if surgery.treatment_episode else 0
    if data.planned_attendances < completed_count:
        return templates.TemplateResponse(
            request,
            "surgeries/form.html",
            surgery_context(
                request,
                current_user,
                surgery.patient,
                surgery=surgery,
                form_data=form_data,
                errors=[f"O total previsto nao pode ser menor que os {completed_count} atendimentos ja registrados."],
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    for field, value in data.model_dump().items():
        setattr(surgery, field, value)
    if surgery.treatment_episode:
        surgery.treatment_episode.started_on = data.surgery_date
    else:
        surgery.treatment_episode = TreatmentEpisode(patient_id=surgery.patient_id, started_on=data.surgery_date)
    db.commit()
    return RedirectResponse(f"/patients/{surgery.patient_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/surgeries/{surgery_id}/delete")
def delete_surgery(
    surgery_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    surgery = get_surgery_or_404(db, surgery_id)
    patient_id = surgery.patient_id
    if surgery.treatment_episode and surgery.treatment_episode.attendances:
        query = urlencode(
            {"error": "Esta cirurgia possui atendimentos vinculados ao ciclo. Exclua ou mova os atendimentos antes."}
        )
        return RedirectResponse(
            f"/patients/{patient_id}?{query}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    if surgery.treatment_episode:
        db.delete(surgery.treatment_episode)
        db.flush()
    db.delete(surgery)
    db.commit()
    return RedirectResponse(f"/patients/{patient_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.patch("/surgeries/{surgery_id}/status")
def patch_surgery_status(
    surgery_id: int,
    payload: SurgeryStatusUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    surgery = get_surgery_or_404(db, surgery_id)
    surgery.status = payload.status
    db.commit()
    return {
        "id": surgery.id,
        "status": surgery.status,
        "surgery_date": surgery.surgery_date.strftime("%d/%m/%Y"),
        "message": "Status da cirurgia atualizado com sucesso.",
    }


@router.post("/surgery-types")
def create_surgery_type(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
):
    try:
        surgery_type = get_or_create_named_option(db, SurgeryType, name)
    except ValueError as exc:
        if not wants_json(request):
            return redirect_to_options(error=str(exc))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not wants_json(request):
        return redirect_to_options(notice="Tipo de cirurgia cadastrado com sucesso.")
    return {"id": surgery_type.id, "name": surgery_type.name}


@router.post("/surgery-types/{surgery_type_id}/edit")
def update_surgery_type(
    surgery_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
):
    try:
        update_named_option(db, SurgeryType, surgery_type_id, name)
    except ValueError as exc:
        return redirect_to_options(error=str(exc))
    return redirect_to_options(notice="Tipo de cirurgia atualizado com sucesso.")


@router.post("/surgery-types/{surgery_type_id}/delete")
def delete_surgery_type(
    surgery_type_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    surgery_type = db.get(SurgeryType, surgery_type_id)
    if not surgery_type:
        raise HTTPException(status_code=404, detail="Tipo de cirurgia nao encontrado.")

    linked_surgeries = db.query(Surgery).filter(Surgery.surgery_type_id == surgery_type.id).count()
    if linked_surgeries:
        return redirect_to_options(
            error="Nao e possivel excluir este tipo de cirurgia porque ha cirurgias vinculadas a ele."
        )

    db.delete(surgery_type)
    db.commit()
    return redirect_to_options(notice="Tipo de cirurgia excluido com sucesso.")


@router.post("/surgeons")
def create_surgeon(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
):
    try:
        surgeon = get_or_create_named_option(db, Surgeon, name)
    except ValueError as exc:
        if not wants_json(request):
            return redirect_to_options(error=str(exc))
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    if not wants_json(request):
        return redirect_to_options(notice="Cirurgiao cadastrado com sucesso.")
    return {"id": surgeon.id, "name": surgeon.name}


@router.post("/surgeons/{surgeon_id}/edit")
def update_surgeon(
    surgeon_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    name: Annotated[str, Form()],
):
    try:
        update_named_option(db, Surgeon, surgeon_id, name)
    except ValueError as exc:
        return redirect_to_options(error=str(exc))
    return redirect_to_options(notice="Cirurgiao atualizado com sucesso.")


@router.post("/surgeons/{surgeon_id}/delete")
def delete_surgeon(
    surgeon_id: int,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
):
    surgeon = db.get(Surgeon, surgeon_id)
    if not surgeon:
        raise HTTPException(status_code=404, detail="Cirurgiao nao encontrado.")

    linked_surgeries = db.query(Surgery).filter(Surgery.surgeon_id == surgeon.id).count()
    linked_attendances = db.query(Attendance).filter(Attendance.surgeon_id == surgeon.id).count()
    if linked_surgeries or linked_attendances:
        return redirect_to_options(
            error="Nao e possivel excluir este cirurgiao porque ha cirurgias ou atendimentos vinculados a ele."
        )

    db.delete(surgeon)
    db.commit()
    return redirect_to_options(notice="Cirurgiao excluido com sucesso.")
