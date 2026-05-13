import os

from sqlalchemy.orm import Session

from app.auth import hash_password
from app.models import User

ADMIN_USERNAME_ENV = "INITIAL_ADMIN_USERNAME"
ADMIN_PASSWORD_ENV = "INITIAL_ADMIN_PASSWORD"
ADMIN_FULL_NAME_ENV = "INITIAL_ADMIN_FULL_NAME"


def create_initial_admin_from_env(db: Session) -> None:
    # O primeiro usuário vem do ambiente para evitar credenciais publicadas no código.
    if db.query(User).count() > 0:
        return

    username = os.getenv(ADMIN_USERNAME_ENV)
    password = os.getenv(ADMIN_PASSWORD_ENV)
    full_name = os.getenv(ADMIN_FULL_NAME_ENV, "Administrador")

    if not username or not password:
        raise RuntimeError(
            "Nenhum usuário existe no banco. Defina INITIAL_ADMIN_USERNAME e "
            "INITIAL_ADMIN_PASSWORD antes da primeira execução."
        )

    if len(password) < 8:
        raise RuntimeError("INITIAL_ADMIN_PASSWORD deve ter pelo menos 8 caracteres.")

    user = User(
        username=username,
        full_name=full_name,
        hashed_password=hash_password(password),
    )
    db.add(user)
    db.commit()
