from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TreatmentEpisode(Base):
    __tablename__ = "treatment_episodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id", ondelete="CASCADE"), nullable=False)
    surgery_id: Mapped[int | None] = mapped_column(
        ForeignKey("surgeries.id", ondelete="SET NULL"),
        unique=True,
        nullable=True,
    )
    started_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    closed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    patient: Mapped["Patient"] = relationship(back_populates="treatment_episodes")
    surgery: Mapped["Surgery | None"] = relationship(back_populates="treatment_episode")
    attendances: Mapped[list["Attendance"]] = relationship(
        back_populates="treatment_episode",
        order_by="desc(Attendance.attendance_date)",
    )
