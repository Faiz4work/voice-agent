"""Pydantic schemas — server-side validation for the patient record.

The voice agent validates conversationally too, but the API must never trust
it: every rule below is enforced here, independently, on every write.
"""
import re
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

US_STATES = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA",
    "KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ",
    "NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT",
    "VA","WA","WV","WI","WY","DC","PR","VI","GU","AS","MP",
}

NAME_RE = re.compile(r"^[A-Za-z][A-Za-z\-' ]{0,49}$")
ZIP_RE = re.compile(r"^\d{5}(-\d{4})?$")

Sex = Literal["Male", "Female", "Other", "Decline to Answer"]


def normalize_phone(v: str) -> str:
    """Strip formatting to 10 digits. Accepts +1/1 country prefix."""
    digits = re.sub(r"\D", "", str(v))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("phone number must be 10 US digits")
    if digits[0] in "01":
        raise ValueError("US area code cannot start with 0 or 1")
    return digits


def normalize_dob(v: Any) -> str:
    """Accept MM/DD/YYYY or YYYY-MM-DD; store ISO. Reject future dates."""
    if isinstance(v, (date, datetime)):
        d = v if isinstance(v, date) else v.date()
    else:
        s = str(v).strip()
        for fmt in ("%m/%d/%Y", "%Y-%m-%d", "%m-%d-%Y", "%B %d, %Y", "%b %d, %Y"):
            try:
                d = datetime.strptime(s, fmt).date()
                break
            except ValueError:
                continue
        else:
            raise ValueError("date of birth must be MM/DD/YYYY")
    if d > date.today():
        raise ValueError("date of birth cannot be in the future")
    if d.year < 1900:
        raise ValueError("date of birth is implausibly old")
    return d.isoformat()


class PatientBase(BaseModel):
    first_name: Annotated[str, Field(min_length=1, max_length=50)]
    last_name: Annotated[str, Field(min_length=1, max_length=50)]
    date_of_birth: str
    sex: Sex
    phone_number: str
    address_line_1: Annotated[str, Field(min_length=1, max_length=200)]
    city: Annotated[str, Field(min_length=1, max_length=100)]
    state: Annotated[str, Field(min_length=2, max_length=2)]
    zip_code: str

    email: EmailStr | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = "English"
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    call_summary: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _valid_name(cls, v: str) -> str:
        v = v.strip()
        if not NAME_RE.match(v):
            raise ValueError("name may contain only letters, hyphens and apostrophes")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _valid_dob(cls, v: Any) -> str:
        return normalize_dob(v)

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def _valid_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state")
    @classmethod
    def _valid_state(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"{v} is not a valid 2-letter US state code")
        return v

    @field_validator("zip_code")
    @classmethod
    def _valid_zip(cls, v: str) -> str:
        v = str(v).strip()
        if not ZIP_RE.match(v):
            raise ValueError("ZIP must be 5 digits or ZIP+4")
        return v


class PatientCreate(PatientBase):
    pass


class PatientUpdate(BaseModel):
    """Partial update — every field optional, same rules when present."""

    first_name: str | None = None
    last_name: str | None = None
    date_of_birth: str | None = None
    sex: Sex | None = None
    phone_number: str | None = None
    address_line_1: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    email: EmailStr | None = None
    address_line_2: str | None = None
    insurance_provider: str | None = None
    insurance_member_id: str | None = None
    preferred_language: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None
    call_summary: str | None = None

    @field_validator("first_name", "last_name")
    @classmethod
    def _valid_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not NAME_RE.match(v):
            raise ValueError("name may contain only letters, hyphens and apostrophes")
        return v

    @field_validator("date_of_birth")
    @classmethod
    def _valid_dob(cls, v: Any) -> str | None:
        return normalize_dob(v) if v else None

    @field_validator("phone_number", "emergency_contact_phone")
    @classmethod
    def _valid_phone(cls, v: str | None) -> str | None:
        return normalize_phone(v) if v else None

    @field_validator("state")
    @classmethod
    def _valid_state(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip().upper()
        if v not in US_STATES:
            raise ValueError(f"{v} is not a valid 2-letter US state code")
        return v

    @field_validator("zip_code")
    @classmethod
    def _valid_zip(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = str(v).strip()
        if not ZIP_RE.match(v):
            raise ValueError("ZIP must be 5 digits or ZIP+4")
        return v


class PatientOut(BaseModel):
    """API representation of a stored patient."""

    model_config = {"from_attributes": True}

    patient_id: str
    first_name: str
    last_name: str
    date_of_birth: str
    sex: str
    phone_number: str
    address_line_1: str
    address_line_2: str | None
    city: str
    state: str
    zip_code: str
    email: str | None
    insurance_provider: str | None
    insurance_member_id: str | None
    preferred_language: str | None
    emergency_contact_name: str | None
    emergency_contact_phone: str | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
