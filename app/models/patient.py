from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(140), index=True, nullable=False)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    health_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    cpf: Mapped[str | None] = mapped_column(String(14), nullable=True, unique=True)
    rg: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    legal_guardian_name: Mapped[str | None] = mapped_column(String(140), nullable=True)
    legal_guardian_cpf: Mapped[str | None] = mapped_column(String(14), nullable=True)
    legal_guardian_relationship: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    attendances: Mapped[list["Attendance"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(Attendance.attendance_date)",
    )
    surgeries: Mapped[list["Surgery"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(Surgery.surgery_date)",
    )
    treatment_episodes: Mapped[list["TreatmentEpisode"]] = relationship(
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="desc(TreatmentEpisode.started_on)",
    )
