import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from starlette.middleware.sessions import SessionMiddleware

from app.database import Base, SessionLocal, engine
from app.routes import attendances, auth, dashboard, patients
from app.seed import create_initial_admin_from_env

load_dotenv()


def get_session_secret() -> str:
    secret_key = os.getenv("SESSION_SECRET_KEY")
    if not secret_key:
        raise RuntimeError("Defina SESSION_SECRET_KEY no ambiente antes de iniciar a aplicacao.")
    if len(secret_key) < 32:
        raise RuntimeError("SESSION_SECRET_KEY deve ter pelo menos 32 caracteres.")
    return secret_key


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        create_initial_admin_from_env(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Gestao de Pacientes - Fisioterapia", lifespan=lifespan)

    app.add_middleware(
        SessionMiddleware,
        secret_key=get_session_secret(),
        same_site="lax",
        https_only=False,
        max_age=60 * 60 * 8,
    )

    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(patients.router)
    app.include_router(attendances.router)

    @app.exception_handler(404)
    def not_found(_: Request, __: Exception):
        return RedirectResponse("/")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
