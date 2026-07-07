"""Nutzer-Datenmodell — individuell, Matrikelnummer-basiert."""

from datetime import datetime
from backend.timeutils import naive_utcnow


from pydantic import BaseModel, Field


class UserRole(str):
    STUDENT = "student"
    INSTRUCTOR = "instructor"      # Case-Approval, Dashboard
    ADMIN = "admin"


class User(BaseModel):
    user_id: str                   # intern generiert
    matrikelnummer: str            # Login-Schlüssel
    display_name: str = ""
    role: str = UserRole.STUDENT
    language: str = "de"           # "de" | "en"
    created_at: datetime = Field(default_factory=naive_utcnow)


class UserCreate(BaseModel):
    matrikelnummer: str
    display_name: str = ""
    language: str = "de"


class UserResponse(BaseModel):
    user_id: str
    matrikelnummer: str
    display_name: str
    role: str
