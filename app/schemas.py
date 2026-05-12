from datetime import date

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginForm(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=4, max_length=128)


class PatientBase(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    birth_date: date
    phone: str = Field(min_length=8, max_length=30)
    email: EmailStr | None = None
    health_info: str = Field(min_length=3, max_length=3000)
    status: str = Field(default="Em tratamento", max_length=30)

    @field_validator("name", "phone", "health_info", "status", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @field_validator("birth_date")
    @classmethod
    def birth_date_cannot_be_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("A data de nascimento nao pode estar no futuro.")
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

    @field_validator("treatment_type", "evolution_notes", mode="before")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class AttendanceCreate(AttendanceBase):
    pass


class AttendanceUpdate(AttendanceBase):
    pass
