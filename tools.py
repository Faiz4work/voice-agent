"""Tools the voice agent can call mid-conversation.

Each handler takes the LLM's arguments and returns a SHORT STRING that the
agent reads back to the caller. They go through the same crud/validation
layer as the REST API — the voice path is never a validation shortcut.

Every handler is defensive: a caller must never hear a stack trace, so
validation problems come back as plain guidance the agent can act on.
"""
import logging
from typing import Any, Callable

from pydantic import ValidationError

import crud
from models import SessionLocal
from schemas import PatientCreate, PatientUpdate, normalize_phone

log = logging.getLogger("voice-agent.tools")

# Human-readable field names for spoken error messages.
FIELD_LABELS = {
    "first_name": "first name",
    "last_name": "last name",
    "date_of_birth": "date of birth",
    "phone_number": "phone number",
    "address_line_1": "street address",
    "zip_code": "ZIP code",
    "state": "state",
    "emergency_contact_phone": "emergency contact phone",
}


def _speak_validation_error(exc: ValidationError) -> str:
    """Turn pydantic errors into one short sentence the agent can re-prompt with."""
    problems = []
    for err in exc.errors():
        field = err["loc"][0] if err["loc"] else "field"
        label = FIELD_LABELS.get(str(field), str(field).replace("_", " "))
        msg = err.get("msg", "").replace("Value error, ", "")
        problems.append(f"{label}: {msg}")
    return "INVALID — please re-ask the caller for " + "; ".join(problems)


def register_patient(args: dict[str, Any]) -> str:
    """Validate and persist a new patient record."""
    try:
        payload = PatientCreate(**args)
    except ValidationError as exc:
        log.warning("register_patient validation failed: %s", exc.errors())
        return _speak_validation_error(exc)

    db = SessionLocal()
    try:
        existing = crud.find_by_phone(db, payload.phone_number)
        if existing:
            return (
                f"DUPLICATE — a record already exists for {existing.first_name} "
                f"{existing.last_name} (patient id {existing.patient_id}). Ask the "
                "caller whether they'd like to update that record instead, and if "
                "so call update_patient with that patient_id."
            )
        patient = crud.create_patient(db, payload)
        log.info("REGISTERED PAYLOAD: %s", payload.model_dump())
        return (
            f"SUCCESS — {patient.first_name} {patient.last_name} is registered. "
            f"Patient ID {patient.patient_id}. Confirm to the caller they're all set."
        )
    except Exception as exc:  # noqa: BLE001 — caller must hear a graceful message
        log.exception("register_patient failed")
        return (
            "ERROR — the record could not be saved. Apologize, tell the caller "
            f"their information was not stored, and offer to try again. ({exc})"
        )
    finally:
        db.close()


def lookup_patient(args: dict[str, Any]) -> str:
    """Find an existing patient by phone number (duplicate detection)."""
    try:
        phone = normalize_phone(args.get("phone_number", ""))
    except ValueError as exc:
        return f"INVALID — {exc}. Ask the caller to repeat their phone number."

    db = SessionLocal()
    try:
        patient = crud.find_by_phone(db, phone)
        if not patient:
            return "NOT_FOUND — no existing record. Proceed with a new registration."
        return (
            f"FOUND — {patient.first_name} {patient.last_name}, DOB "
            f"{patient.date_of_birth}, patient id {patient.patient_id}. Ask if they "
            "want to update this record instead of creating a new one."
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("lookup_patient failed")
        return f"ERROR — lookup unavailable, continue with registration. ({exc})"
    finally:
        db.close()


def update_patient(args: dict[str, Any]) -> str:
    """Update fields on an existing patient (partial)."""
    patient_id = args.pop("patient_id", None)
    if not patient_id:
        return "ERROR — patient_id is required. Look the patient up first."
    try:
        payload = PatientUpdate(**args)
    except ValidationError as exc:
        return _speak_validation_error(exc)

    db = SessionLocal()
    try:
        patient = crud.get_patient(db, str(patient_id))
        if patient is None:
            return "NOT_FOUND — no patient with that id. Offer a new registration."
        updated = crud.update_patient(db, patient, payload)
        return (
            f"SUCCESS — {updated.first_name} {updated.last_name}'s record is updated. "
            "Confirm the change to the caller."
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("update_patient failed")
        return f"ERROR — the update could not be saved. Apologize to the caller. ({exc})"
    finally:
        db.close()


TOOL_REGISTRY: dict[str, Callable[[dict[str, Any]], str]] = {
    "register_patient": register_patient,
    "lookup_patient": lookup_patient,
    "update_patient": update_patient,
}
