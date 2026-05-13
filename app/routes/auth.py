from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.auth import authenticate_user, login_user, logout_user
from app.database import get_db
from app.schemas import LoginForm

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/login")
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(request, "auth/login.html")


@router.post("/login")
def login(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    try:
        credentials = LoginForm(username=username, password=password)
    except ValidationError:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Informe usuário e senha válidos.",
                "username": username,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Usuário ou senha incorretos.",
                "username": credentials.username,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    login_user(request, user)
    return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
def logout(request: Request):
    logout_user(request)
    return RedirectResponse("/login", status_code=status.HTTP_303_SEE_OTHER)
