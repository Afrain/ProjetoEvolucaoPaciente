from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
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
    service_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    contracted_procedure: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    package_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    installment_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installment_due_dates: Mapped[str | None] = mapped_column(Text, nullable=True)
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
