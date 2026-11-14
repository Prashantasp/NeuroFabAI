from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import get_settings

# Rejecting only "short" passwords lets `password1` through. These are the
# credentials that actually appear in breach lists for a product like this.
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "1234567890",
    "qwertyuiop", "letmein", "welcome1", "admin123", "changeme", "iloveyou",
    "neurofab", "neurofab123",
}


def validate_password_strength(password: str) -> str:
    settings = get_settings()
    problems = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        problems.append(f"be at least {settings.PASSWORD_MIN_LENGTH} characters")
    if len(password) > settings.PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be at most {settings.PASSWORD_MAX_LENGTH} characters."
        )
    if not any(c.islower() for c in password):
        problems.append("include a lowercase letter")
    if not any(c.isupper() for c in password):
        problems.append("include an uppercase letter")
    if not any(c.isdigit() for c in password):
        problems.append("include a number")
    if password.lower() in COMMON_PASSWORDS:
        raise ValueError("That password is too common. Please choose a different one.")

    if problems:
        raise ValueError("Password must " + ", ".join(problems) + ".")
    return password


class UserBase(BaseModel):
    email: EmailStr
    username: Optional[str] = Field(None, max_length=50)
    full_name: Optional[str] = Field(None, max_length=120)
    company: Optional[str] = Field(None, max_length=120)


class UserCreate(UserBase):
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    """Profile fields a user may change about themselves.

    Deliberately excludes `role`, `is_active`, and `is_verified` -- those are
    privilege fields and must never be settable from a self-service endpoint.
    """

    full_name: Optional[str] = Field(None, max_length=120)
    company: Optional[str] = Field(None, max_length=120)
    username: Optional[str] = Field(None, max_length=50)
    avatar_url: Optional[str] = Field(None, max_length=512)


class PasswordChange(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1, max_length=128)

    @field_validator("new_password")
    @classmethod
    def _check_password(cls, v: str) -> str:
        return validate_password_strength(v)


class UserRead(UserBase):
    id: str
    role: str
    is_active: bool
    is_verified: bool
    avatar_url: Optional[str] = None
    last_login: Optional[datetime] = None
    last_workspace_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
