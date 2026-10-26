"""Separate scheduling tables; no changes to existing patient records."""
import uuid
from sqlalchemy import String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from models import Base

class Appointment(Base):
    __tablename__ = 'appointments'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[str] = mapped_column(String(40), index=True)
    service_id: Mapped[str] = mapped_column(String(60))
    starts_at: Mapped[str] = mapped_column(String(40))
    active_slot: Mapped[str | None] = mapped_column(String(40))
    customer_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(254))
    address: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default='confirmed')
    idempotency_key: Mapped[str] = mapped_column(String(120))
    fingerprint: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('business_id', 'active_slot', name='uq_business_active_slot'), UniqueConstraint('business_id', 'idempotency_key', name='uq_business_booking_key'))

class Inquiry(Base):
    __tablename__ = 'inquiries'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    business_id: Mapped[str] = mapped_column(String(40), index=True)
    customer_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default='new')
    created_at: Mapped[str] = mapped_column(String(40))
