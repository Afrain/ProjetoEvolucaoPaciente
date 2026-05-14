from datetime import date

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator

ATTENDANCE_LOCATION_OPTIONS = ["Consultorio", "Domiciliar"]
ATTENDANCE_STATUS_OPTIONS = ["Em andamento", "Alta", "Pausado"]
SURGERY_STATUS_OPTIONS = ["Em progresso", "Alta"]


def validation_messages(exc: ValidationError, field_labels: dict[str, str]) -> list[str]:
    messages = []
    for error in exc.errors():
        field = str(error["loc"][-1])
        label = field_labels.get(field, "Campo")
        error_type = error["type"]
        ctx = error.get("ctx") or {}

        if error_type == "missing":
            messages.append(f"{label} e obrigatorio.")
        elif error_type == "string_type":
            messages.append(f"{label} e obrigatorio.")
        elif error_type == "string_too_short":
            min_length = ctx.get("min_length", 1)
            if min_length == 1:
                messages.append(f"{label} e obrigatorio.")
            else:
                messages.append(f"{label} deve ter pelo menos {min_length} caractere(s).")
        elif error_type == "string_too_long":
            messages.append(f"{label} deve ter no maximo {ctx.get('max_length')} caractere(s).")
        elif error_type == "greater_than_equal":
            messages.append(f"{label} deve ser maior ou igual a {ctx.get('ge')}.")
        elif error_type == "less_than_equal":
            messages.append(f"{label} deve ser menor ou igual a {ctx.get('le')}.")
        elif error_type == "int_parsing":
            messages.append(f"{label} deve ser um numero valido.")
        elif error_type == "date_from_datetime_parsing":
            messages.append(f"{label} deve ser uma data valida.")
        elif error_type == "value_error" and "error" in ctx:
            messages.append(str(ctx["error"]))
        else:
            messages.append(f"{label} contem um valor invalido.")
    return messages


class LoginForm(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class PatientBase(BaseModel):
    name: str = Field(min_length=1, max_length=140)
    birth_date: date | None = None
    phone: str | None = Field(default=None, max_length=30)
    health_info: str | None = Field(default=None, max_length=3000)

    @field_validator("name", "phone", "health_info", mode="before")
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
            raise ValueError("A data de nascimento nao pode estar no futuro.")
        return value


class PatientCreate(PatientBase):
    pass


class PatientUpdate(PatientBase):
    pass


class AttendanceBase(BaseModel):
    treatment_episode_id: int = Field(ge=1)
    attendance_date: date
    location: str = Field(default="Consultorio", max_length=20)
    treatment_type: str = Field(min_length=2, max_length=120)
    evolution_notes: str = Field(min_length=3, max_length=3000)

    @field_validator("location", "treatment_type", "evolution_notes", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("location")
    @classmethod
    def location_must_be_valid(cls, value: str | None) -> str:
        value = value or "Consultorio"
        if value not in ATTENDANCE_LOCATION_OPTIONS:
            raise ValueError("Selecione um local de atendimento valido.")
        return value

class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(AttendanceBase):
    status: str = Field(default="Em andamento", max_length=20)

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: str | None) -> str:
        if not isinstance(value, str):
            return "Em andamento"
        return value.strip() or "Em andamento"

    @field_validator("status")
    @classmethod
    def status_must_be_valid(cls, value: str) -> str:
        if value not in ATTENDANCE_STATUS_OPTIONS:
            raise ValueError("Selecione um status de atendimento valido.")
        return value


class SurgeryBase(BaseModel):
    surgery_date: date
    surgery_type_id: int = Field(ge=1)
    surgeon_id: int = Field(ge=1)
    planned_attendances: int = Field(ge=1, le=500)
    status: str = Field(default="Em progresso", max_length=20)

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: str | None) -> str:
        if not isinstance(value, str):
            return "Em progresso"
        return value.strip() or "Em progresso"

    @field_validator("status")
    @classmethod
    def surgery_status_must_be_valid(cls, value: str) -> str:
        if value not in SURGERY_STATUS_OPTIONS:
            raise ValueError("Selecione um status de cirurgia valido.")
        return value


class SurgeryCreate(SurgeryBase):
    pass


class SurgeryUpdate(SurgeryBase):
    pass


class SurgeryStatusUpdate(BaseModel):
    status: str = Field(max_length=20)

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in SURGERY_STATUS_OPTIONS:
            raise ValueError("Selecione um status de cirurgia valido.")
        return value


class EpisodeStatusUpdate(BaseModel):
    status: str = Field(max_length=20)

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: str | None) -> str:
        if not isinstance(value, str):
            return ""
        return value.strip()

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value != "Alta":
            raise ValueError("Apenas a transicao manual para 'Alta' e permitida neste endpoint.")
        return value
