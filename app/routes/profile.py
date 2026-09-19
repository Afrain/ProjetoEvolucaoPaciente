from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import ProfessionalProfile, User
from app.schemas import ProfessionalProfileUpdate, validation_messages

router = APIRouter(prefix="/profile", tags=["profile"])
templates = Jinja2Templates(directory="templates")

PROFILE_FIELD_LABELS = {
    "cpf_cnpj": "CPF/CNPJ",
    "crefito": "CREFITO",
    "professional_address": "Endereço profissional",
    "professional_email": "E-mail profissional",
}


def profile_context(
    request: Request,
    current_user: User,
    profile: ProfessionalProfile | None,
    *,
    form_data: dict | None = None,
    errors: list[str] | None = None,
    notice: str = "",
) -> dict:
    return {
        "request": request,
        "current_user": current_user,
        "profile": profile,
        "form_data": form_data or {},
        "errors": errors or [],
        "notice": notice,
    }


@router.get("")
def get_profile(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    notice: str = "",
):
    profile = db.query(ProfessionalProfile).filter(ProfessionalProfile.user_id == current_user.id).first()
    return templates.TemplateResponse(
        request,
        "profile/form.html",
        profile_context(request, current_user, profile, notice=notice),
    )


@router.post("")
def update_profile(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    cpf_cnpj: Annotated[str, Form()] = "",
    crefito: Annotated[str, Form()] = "",
    professional_address: Annotated[str, Form()] = "",
    professional_email: Annotated[str, Form()] = "",
):
    form_data = {
        "cpf_cnpj": cpf_cnpj,
        "crefito": crefito,
        "professional_address": professional_address,
        "professional_email": professional_email,
    }
    profile = db.query(ProfessionalProfile).filter(ProfessionalProfile.user_id == current_user.id).first()
    try:
        data = ProfessionalProfileUpdate(**form_data)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "profile/form.html",
            profile_context(
                request,
                current_user,
                profile,
                form_data=form_data,
                errors=validation_messages(exc, PROFILE_FIELD_LABELS),
            ),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    try:
        if profile is None:
            profile = ProfessionalProfile(user_id=current_user.id)
            db.add(profile)
        for field, value in data.model_dump().items():
            setattr(profile, field, value)
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "profile/form.html",
            profile_context(
                request,
                current_user,
                profile,
                form_data=form_data,
                errors=["Não foi possível salvar o perfil profissional. Tente novamente."],
            ),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    return RedirectResponse(
        "/profile?notice=Perfil%20profissional%20salvo%20com%20sucesso.",
        status_code=status.HTTP_303_SEE_OTHER,
    )
