from datetime import date

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator

LOCATION_OPTIONS = ["Consultório", "Domiciliar"]
STATUS_OPTIONS = ["Em tratamento", "Alta", "Pausado"]


def validation_messages(exc: ValidationError, field_labels: dict[str, str]) -> list[str]:
    messages = []
    for error in exc.errors():
        field = str(error["loc"][-1])
        label = field_labels.get(field, "Campo")
        error_type = error["type"]
        ctx = error.get("ctx") or {}

        if error_type == "missing":
            messages.append(f"{label} é obrigatório.")
        elif error_type == "string_type":
            messages.append(f"{label} é obrigatório.")
        elif error_type == "string_too_short":
            min_length = ctx.get("min_length", 1)
            if min_length == 1:
                messages.append(f"{label} é obrigatório.")
            else:
                messages.append(f"{label} deve ter pelo menos {min_length} caractere(s).")
        elif error_type == "string_too_long":
            messages.append(f"{label} deve ter no máximo {ctx.get('max_length')} caractere(s).")
        elif error_type == "greater_than_equal":
            messages.append(f"{label} deve ser maior ou igual a {ctx.get('ge')}.")
        elif error_type == "less_than_equal":
            messages.append(f"{label} deve ser menor ou igual a {ctx.get('le')}.")
        elif error_type == "int_parsing":
            messages.append(f"{label} deve ser um número válido.")
        elif error_type == "date_from_datetime_parsing":
            messages.append(f"{label} deve ser uma data válida.")
        elif error_type == "value_error" and "error" in ctx:
            messages.append(str(ctx["error"]))
        else:
            messages.append(f"{label} contém um valor inválido.")
    return messages


class LoginForm(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class PatientBase(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    health_info: str | None = Field(default=None, max_length=3000)
    status: str = Field(default="Em tratamento", max_length=30)
    location: str = Field(default="Consultório", max_length=20)

    @field_validator("name", "phone", "health_info", "status", "location", mode="before")
    @classmethod
    def strip_text(cls, value: str, info: ValidationInfo) -> str | None:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value and info.field_name in {"phone", "health_info"}:
            return None
        return value

    @field_validator("birth_date", mode="before")
    @classmethod
    def empty_birth_date_to_none(cls, value: str | date | None) -> date | None:
        if value == "":
            return None
        return value

    @field_validator("birth_date")
    @classmethod
    def birth_date_cannot_be_future(cls, value: date | None) -> date | None:
        if value and value > date.today():
            raise ValueError("A data de nascimento não pode estar no futuro.")
        return value

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, value: str | None) -> str:
        value = value or "Em tratamento"
        if value not in STATUS_OPTIONS:
            raise ValueError("Selecione um status válido.")
        return value

    @field_validator("location")
    @classmethod
    def location_must_be_valid(cls, value: str | None) -> str:
        value = value or "Consultório"
        if value not in LOCATION_OPTIONS:
            raise ValueError("Selecione um local de atendimento válido.")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    pass


class AttendanceBase(BaseModel):
    attendance_date: date
    duration_minutes: int = Field(ge=1, le=600)
    treatment_type: str = Field(min_length=2, max_length=120)
    evolution_notes: str = Field(min_length=3, max_length=3000)
    surgeon_id: int | None = None

    @field_validator("treatment_type", "evolution_notes", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("surgeon_id", mode="before")
    @classmethod
    def empty_surgeon_to_none(cls, value: str | int | None) -> int | None:
        if value == "":
            return None
        return value


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(AttendanceBase):
    pass


class SurgeryBase(BaseModel):
    surgery_date: date
    surgery_type_id: int = Field(ge=1)
    surgeon_id: int = Field(ge=1)


class SurgeryCreate(SurgeryBase):
    pass


class SurgeryUpdate(SurgeryBase):
    pass
