from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SurgeryType(Base):
    __tablename__ = "surgery_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="surgery_type")


class Surgeon(Base):
    __tablename__ = "surgeons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(140), unique=True, index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    surgeries: Mapped[list["Surgery"]] = relationship(back_populates="surgeon")
    attendances: Mapped[list["Attendance"]] = relationship(back_populates="surgeon")


class Surgery(Base):
    __tablename__ = "surgeries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    surgery_type_id: Mapped[int] = mapped_column(ForeignKey("surgery_types.id"), nullable=False)
    surgeon_id: Mapped[int] = mapped_column(ForeignKey("surgeons.id"), nullable=False)
    surgery_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    planned_attendances: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Em tratamento")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="surgeries")
    surgery_type: Mapped[SurgeryType] = relationship(back_populates="surgeries")
    surgeon: Mapped[Surgeon] = relationship(back_populates="surgeries")
    treatment_episode: Mapped["TreatmentEpisode | None"] = relationship(
        back_populates="surgery",
        uselist=False,
    )
