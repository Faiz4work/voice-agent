"""SQLAlchemy models — the persistent patient demographic record.

One table, `patients`, matching the required US patient minimum demographic
dataset. Works identically on SQLite (local dev) and PostgreSQL (Supabase in
production) because we only use portable column types.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

import os

# SQLite locally, Postgres (Supabase) in production — same models either way.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./patients.db")
# SQLAlchemy needs the postgresql:// scheme; Supabase/Heroku hand out postgres://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


SEXES = ("Male", "Female", "Other", "Decline to Answer")


class Patient(Base):
    __tablename__ = "patients"

    # --- identity -------------------------------------------------------
    patient_id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )

    # --- required demographics -----------------------------------------
    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    date_of_birth: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    sex: Mapped[str] = mapped_column(String(20), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    address_line_1: Mapped[str] = mapped_column(String(200), nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)
    zip_code: Mapped[str] = mapped_column(String(10), nullable=False)

    # --- optional -------------------------------------------------------
    email: Mapped[str | None] = mapped_column(String(254))
    address_line_2: Mapped[str | None] = mapped_column(String(200))
    insurance_provider: Mapped[str | None] = mapped_column(String(120))
    insurance_member_id: Mapped[str | None] = mapped_column(String(60))
    preferred_language: Mapped[str | None] = mapped_column(String(50), default="English")
    emergency_contact_name: Mapped[str | None] = mapped_column(String(120))
    emergency_contact_phone: Mapped[str | None] = mapped_column(String(10))

    # --- observability: transcript/summary of the call that created this -
    call_summary: Mapped[str | None] = mapped_column(Text)

    # --- timestamps -----------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    # Soft delete — DELETE /patients/:id sets this; rows are never removed.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        CheckConstraint(f"sex IN {SEXES}", name="ck_patients_sex"),
        Index("ix_patients_last_name", "last_name"),
        Index("ix_patients_dob", "date_of_birth"),
    )


def init_db() -> None:
    """Create tables if absent. Safe to call on every boot."""
    Base.metadata.create_all(engine)
