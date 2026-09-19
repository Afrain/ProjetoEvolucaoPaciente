from datetime import date
from decimal import Decimal
import json
import re

from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator, model_validator

ATTENDANCE_LOCATION_OPTIONS = ["Consultorio", "Domiciliar"]
SURGERY_IN_TREATMENT_STATUS = "Em tratamento"
SURGERY_LEGACY_IN_PROGRESS_STATUS = "Em progresso"
SURGERY_STATUS_OPTIONS = [SURGERY_IN_TREATMENT_STATUS, "Alta"]
SERVICE_TYPE_OPTIONS = ["Avulso", "Pacote", "Outro"]
PAYMENT_METHOD_OPTIONS = [
    "Dinheiro",
    "Pix",
    "Cartão de débito",
    "Cartão de crédito",
    "Transferência bancária",
    "Outro",
]
PAYMENT_CONDITION_OPTIONS = ["À vista", "Parcelado"]

CPF_PATTERN = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
CNPJ_PATTERN = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_surgery_status(value: str) -> str:
    if value == SURGERY_LEGACY_IN_PROGRESS_STATUS:
        return SURGERY_IN_TREATMENT_STATUS
    return value


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
        elif error_type in {"decimal_parsing", "decimal_type"}:
            messages.append(f"{label} deve ser um valor monetario valido.")
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
    cpf: str | None = Field(default=None, max_length=14)
    rg: str | None = Field(default=None, max_length=20)
    address: str | None = Field(default=None, max_length=300)
    email: str | None = Field(default=None, max_length=120)
    legal_guardian_name: str | None = Field(default=None, max_length=140)
    legal_guardian_cpf: str | None = Field(default=None, max_length=14)
    legal_guardian_relationship: str | None = Field(default=None, max_length=60)

    @field_validator(
        "name",
        "phone",
        "health_info",
        "cpf",
        "rg",
        "address",
        "email",
        "legal_guardian_name",
        "legal_guardian_cpf",
        "legal_guardian_relationship",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: str, info: ValidationInfo) -> str | None:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value and info.field_name != "name":
            return None
        return value

    @field_validator("cpf", "legal_guardian_cpf")
    @classmethod
    def cpf_must_be_formatted(cls, value: str | None, info: ValidationInfo) -> str | None:
        if value and not CPF_PATTERN.fullmatch(value):
            label = "CPF do responsável legal" if info.field_name == "legal_guardian_cpf" else "CPF"
            raise ValueError(f"{label} deve estar no formato 000.000.000-00.")
        return value

    @field_validator("email")
    @classmethod
    def email_must_be_valid(cls, value: str | None) -> str | None:
        if value and not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("E-mail deve conter @ seguido de domínio válido.")
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


class ProfessionalProfileUpdate(BaseModel):
    cpf_cnpj: str | None = Field(default=None, max_length=18)
    crefito: str | None = Field(default=None, max_length=30)
    professional_address: str | None = Field(default=None, max_length=300)
    professional_email: str | None = Field(default=None, max_length=120)

    @field_validator("cpf_cnpj", "crefito", "professional_address", "professional_email", mode="before")
    @classmethod
    def empty_text_to_none(cls, value: str | None, info: ValidationInfo) -> str | None:
        if not isinstance(value, str):
            return value
        if not value.strip():
            return None
        return value.strip() if info.field_name == "crefito" else value

    @field_validator("cpf_cnpj")
    @classmethod
    def cpf_cnpj_must_be_formatted(cls, value: str | None) -> str | None:
        if not value:
            return value
        digits = re.sub(r"\D", "", value)
        accepted_input = (
            value.isdigit()
            or CPF_PATTERN.fullmatch(value) is not None
            or CNPJ_PATTERN.fullmatch(value) is not None
        )
        if not accepted_input or len(digits) not in {11, 14}:
            raise ValueError("CPF/CNPJ deve estar no formato 000.000.000-00 ou 00.000.000/0000-00.")
        return digits

    @field_validator("professional_email")
    @classmethod
    def professional_email_must_be_valid(cls, value: str | None) -> str | None:
        if value and not EMAIL_PATTERN.fullmatch(value):
            raise ValueError("E-mail profissional deve conter @ seguido de domínio válido.")
        return value


class EpisodeContractDataUpdate(BaseModel):
    service_type: str | None = Field(default=None, max_length=30)
    contracted_procedure: str | None = Field(default=None, max_length=1000)
    session_value: Decimal | None = Field(default=None, ge=Decimal("0.01"), le=Decimal("999999.99"))
    package_value: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("999999.99"))
    payment_method: str | None = Field(default=None, max_length=40)
    payment_condition: str | None = Field(default=None, max_length=20)
    installment_count: int | None = Field(default=None, ge=2, le=60)
    installment_due_dates: list[date] | None = Field(default=None, max_length=60)

    @field_validator("service_type", "contracted_procedure", "payment_method", "payment_condition", mode="before")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        if not isinstance(value, str):
            return value
        return value if value.strip() else None

    @field_validator("session_value", "package_value", "installment_count", mode="before")
    @classmethod
    def optional_number(cls, value):
        return None if value == "" or value is None else value

    @field_validator("installment_due_dates", mode="before")
    @classmethod
    def parse_installment_due_dates(cls, value):
        if value is None or value == "":
            return None
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError("Datas das parcelas devem ser válidas.") from exc
        if not isinstance(value, list):
            raise ValueError("Datas das parcelas devem ser uma lista.")
        return value or None

    @field_validator("service_type")
    @classmethod
    def service_type_must_be_valid(cls, value: str | None) -> str | None:
        if value and value not in SERVICE_TYPE_OPTIONS:
            raise ValueError("Tipo de serviço inválido.")
        return value

    @field_validator("payment_method")
    @classmethod
    def payment_method_must_be_valid(cls, value: str | None) -> str | None:
        if value and value not in PAYMENT_METHOD_OPTIONS:
            raise ValueError("Forma de pagamento inválida.")
        return value

    @field_validator("payment_condition")
    @classmethod
    def payment_condition_must_be_valid(cls, value: str | None) -> str | None:
        if value and value not in PAYMENT_CONDITION_OPTIONS:
            raise ValueError("Condição de pagamento inválida.")
        return value

    @model_validator(mode="after")
    def clear_installments_for_cash_payment(self):
        if self.payment_condition != "Parcelado":
            self.installment_count = None
            self.installment_due_dates = None
        return self


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
    pass


class SurgeryBase(BaseModel):
    surgery_date: date
    surgery_type_id: int = Field(ge=1)
    surgeon_id: int = Field(ge=1)
    planned_attendances: int = Field(ge=1, le=500)
    status: str = Field(default=SURGERY_IN_TREATMENT_STATUS, max_length=20)

    @field_validator("status", mode="before")
    @classmethod
    def strip_status(cls, value: str | None) -> str:
        if not isinstance(value, str):
            return SURGERY_IN_TREATMENT_STATUS
        return normalize_surgery_status(value.strip() or SURGERY_IN_TREATMENT_STATUS)

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
        return normalize_surgery_status(value.strip())

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
