"""REST API for patient records.

Every response uses the envelope {"data": ..., "error": ...} and proper HTTP
status codes (200/201/400/404/422/500).
"""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

import crud
from models import SessionLocal
from schemas import PatientCreate, PatientOut, PatientUpdate, normalize_phone

router = APIRouter(prefix="/patients", tags=["patients"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ok(data: Any) -> dict[str, Any]:
    return {"data": data, "error": None}


def _serialize(p) -> dict[str, Any]:
    return PatientOut.model_validate(p).model_dump(mode="json")


@router.get("")
def list_patients(
    db: Session = Depends(get_db),
    last_name: str | None = Query(None),
    date_of_birth: str | None = Query(None, description="YYYY-MM-DD or MM/DD/YYYY"),
    phone_number: str | None = Query(None),
    include_deleted: bool = Query(False),
):
    """List patients, with optional filters."""
    if date_of_birth:
        from schemas import normalize_dob

        try:
            date_of_birth = normalize_dob(date_of_birth)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if phone_number:
        try:
            phone_number = normalize_phone(phone_number)
        except ValueError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    rows = crud.list_patients(db, last_name, date_of_birth, phone_number, include_deleted)
    return ok([_serialize(p) for p in rows])


@router.get("/{patient_id}")
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return ok(_serialize(patient))


@router.post("", status_code=status.HTTP_201_CREATED)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    patient = crud.create_patient(db, payload)
    return ok(_serialize(patient))


@router.put("/{patient_id}")
def update_patient(
    patient_id: str, payload: PatientUpdate, db: Session = Depends(get_db)
):
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    return ok(_serialize(crud.update_patient(db, patient, payload)))


@router.delete("/{patient_id}")
def delete_patient(patient_id: str, db: Session = Depends(get_db)):
    """Soft delete — sets deleted_at, keeps the row."""
    patient = crud.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Patient not found")
    crud.soft_delete_patient(db, patient)
    return ok({"patient_id": patient_id, "deleted": True})
