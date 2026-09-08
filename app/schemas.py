from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
)

from app.models import ApplicationStatus, FeeStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Topic = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ParticipantCreate(InputModel):
    full_name: Name
    email: EmailStr
    organization: Name | None = None
    password: str = Field(min_length=12, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value):
        return str(value).lower()

    @field_validator("password")
    @classmethod
    def meaningful_password(cls, value):
        if not value.strip():
            raise ValueError("Password must not consist only of whitespace")
        return value


class ParticipantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: EmailStr
    organization: str | None = None
    role: str = Field(validation_alias="access_role")


class ApplicationCreate(InputModel):
    participant_id: int | None = Field(default=None, gt=0)
    topic: Topic


class ApplicationStatusUpdate(InputModel):
    status: ApplicationStatus


class FeeCreate(InputModel):
    application_id: int = Field(gt=0)
    amount: float = Field(gt=0, le=9999999999.99, allow_inf_nan=False)

    @field_validator("amount")
    @classmethod
    def monetary_precision(cls, value):
        if Decimal(str(value)).as_tuple().exponent < -2:
            raise ValueError("Amount must have at most two decimal places")
        return value


class FeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    application_id: int
    amount: float
    status: FeeStatus
    paid_at: datetime | None = None


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    participant_id: int
    topic: str
    status: ApplicationStatus
    submitted_at: datetime
    fee: FeeOut | None = None
