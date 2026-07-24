"""Data-access layer.

Shared by BOTH the REST API and the voice agent's tool calls, so a patient
registered by phone and one created via POST /patients go through identical
validation and persistence. Soft-deleted rows are excluded everywhere by
default.
"""
import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Patient, utcnow
from schemas import PatientCreate, PatientUpdate

log = logging.getLogger("voice-agent.crud")


def list_patients(
    db: Session,
    last_name: str | None = None,
    date_of_birth: str | None = None,
    phone_number: str | None = None,
    include_deleted: bool = False,
) -> list[Patient]:
    stmt = select(Patient)
    if not include_deleted:
        stmt = stmt.where(Patient.deleted_at.is_(None))
    if last_name:
        stmt = stmt.where(Patient.last_name.ilike(last_name))
    if date_of_birth:
        stmt = stmt.where(Patient.date_of_birth == date_of_birth)
    if phone_number:
        stmt = stmt.where(Patient.phone_number == phone_number)
    return list(db.scalars(stmt.order_by(Patient.created_at.desc())))


def get_patient(db: Session, patient_id: str) -> Patient | None:
    p = db.get(Patient, patient_id)
    return None if (p is None or p.deleted_at is not None) else p


def find_by_phone(db: Session, phone_number: str) -> Patient | None:
    """Used for duplicate detection on inbound calls."""
    return db.scalars(
        select(Patient)
        .where(Patient.phone_number == phone_number, Patient.deleted_at.is_(None))
        .order_by(Patient.created_at.desc())
    ).first()


def create_patient(db: Session, data: PatientCreate) -> Patient:
    patient = Patient(**data.model_dump(exclude_none=False))
    db.add(patient)
    db.commit()
    db.refresh(patient)
    log.info("Patient created: %s %s (%s)", patient.first_name, patient.last_name,
             patient.patient_id)
    return patient


def update_patient(db: Session, patient: Patient, data: PatientUpdate) -> Patient:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(patient, field, value)
    patient.updated_at = utcnow()
    db.commit()
    db.refresh(patient)
    log.info("Patient updated: %s (%s)", patient.patient_id, list(changes))
    return patient


def soft_delete_patient(db: Session, patient: Patient) -> Patient:
    """Never hard-delete: set deleted_at so the row remains auditable."""
    patient.deleted_at = utcnow()
    db.commit()
    db.refresh(patient)
    log.info("Patient soft-deleted: %s", patient.patient_id)
    return patient
