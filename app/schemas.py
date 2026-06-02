"""
EduProctorAI - Pydantic Schemas
"""
from pydantic import BaseModel, field_validator, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import re


class UserCreate(BaseModel):
    iin: str = Field(..., min_length=12, max_length=12)
    password: str = Field(..., min_length=6)
    full_name: str = Field(..., min_length=2)
    role: str = "student"
    group_name: Optional[str] = None
    language: str = "en"

    @field_validator('iin')
    @classmethod
    def validate_iin(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError('ИИН должен содержать только цифры')
        if len(v) != 12:
            raise ValueError('ИИН должен состоять из 12 цифр')
        return v


class UserResponse(BaseModel):
    id: int
    iin: str
    full_name: str
    role: str
    group_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    language: str = "en"
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    group_name: Optional[str] = None
    is_active: Optional[bool] = None
    language: Optional[str] = None


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str
    iin: str
    language: str = "en"


class GroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    student_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class MaterialUploadResponse(BaseModel):
    message: str
    material_id: int
    title: str
    rk1_questions: int
    rk2_questions: int
    final_questions: int
    lectures_count: int


class GenerateWrittenRequest(BaseModel):
    material_id: int
    test_type: str
    group_name: str
    title: Optional[str] = None
    language: str = "en"


class GenerateWrittenResponse(BaseModel):
    message: str
    test_id: int
    questions: List[Dict]
    questions_count: int
    source_material: str


class TestSubmitResponse(BaseModel):
    result_id: int
    score: float
    max_score: float
    percentage: float
    letter_grade: str
    gpa: float
    movement_count: int
    window_switches: int
    penalty_points: float
    final_score: float