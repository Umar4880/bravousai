import uuid

from pydantic import BaseModel, Field, field_validator


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("Enter a valid email address.")
    return email


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=128)
    email: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class SigninRequest(BaseModel):
    email: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return normalize_email(value)


class AuthResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    email: str
