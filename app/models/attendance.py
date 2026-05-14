from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Attendance(Base):
    __tablename__ = "attendances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    treatment_episode_id: Mapped[int | None] = mapped_column(
        ForeignKey("treatment_episodes.id", ondelete="SET NULL"),
        nullable=True,
    )
    surgeon_id: Mapped[int | None] = mapped_column(ForeignKey("surgeons.id", ondelete="SET NULL"), nullable=True)
    attendance_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    location: Mapped[str] = mapped_column(String(20), default="Consultorio", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="Em andamento", nullable=False)
    treatment_type: Mapped[str] = mapped_column(String(120), nullable=False)
    evolution_notes: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    patient: Mapped["Patient"] = relationship(back_populates="attendances")
    treatment_episode: Mapped["TreatmentEpisode | None"] = relationship(back_populates="attendances")
    surgeon: Mapped["Surgeon | None"] = relationship(back_populates="attendances")
