"""
EduProctorAI - SQLAlchemy Database Models
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    iin = Column(String(12), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="student")
    group_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    test_results = relationship("TestResult", back_populates="student", cascade="all, delete-orphan")
    proctor_sessions = relationship("ProctorSession", back_populates="student", cascade="all, delete-orphan")
    written_submissions = relationship("WrittenSubmission", foreign_keys="WrittenSubmission.student_id", back_populates="student", cascade="all, delete-orphan")
    graded_written = relationship("WrittenSubmission", foreign_keys="WrittenSubmission.graded_by", back_populates="grader")
    created_tests = relationship("Test", back_populates="creator")
    created_materials = relationship("EducationalMaterial", back_populates="creator")


class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, index=True, nullable=False)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EducationalMaterial(Base):
    __tablename__ = "educational_materials"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    file_path = Column(String(500), nullable=False)
    extracted_text = Column(Text, nullable=True)
    rk1_questions = Column(JSON, nullable=True)
    rk2_questions = Column(JSON, nullable=True)
    final_questions = Column(JSON, nullable=True)
    lecture_texts = Column(JSON, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    creator = relationship("User", back_populates="created_materials")
    generated_tests = relationship("Test", back_populates="source_material")


class Test(Base):
    __tablename__ = "tests"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    format = Column(String(50), nullable=False)
    description = Column(Text, nullable=True)
    questions = Column(JSON, nullable=False)
    max_score = Column(Float, nullable=False, default=100)
    time_limit_minutes = Column(Integer, nullable=False)
    passing_score = Column(Float, nullable=False, default=50)
    max_attempts = Column(Integer, nullable=False, default=1)
    created_by = Column(Integer, ForeignKey("users.id"))
    source_material_id = Column(Integer, ForeignKey("educational_materials.id"), nullable=True)
    group_name = Column(String(100), nullable=True)
    assigned_students = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    creator = relationship("User", back_populates="created_tests")
    source_material = relationship("EducationalMaterial", back_populates="generated_tests")
    results = relationship("TestResult", back_populates="test", cascade="all, delete-orphan")
    written_submissions = relationship("WrittenSubmission", back_populates="test", cascade="all, delete-orphan")


class TestResult(Base):
    __tablename__ = "test_results"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    test_id = Column(Integer, ForeignKey("tests.id"))
    score = Column(Float, nullable=False, default=0)
    max_score = Column(Float, nullable=False)
    percentage = Column(Float, nullable=False, default=0)
    letter_grade = Column(String(2), nullable=True)
    gpa = Column(Float, nullable=True, default=0)
    answers = Column(JSON, nullable=True)
    proctor_notes = Column(JSON, nullable=True)
    plagiarism_report = Column(JSON, nullable=True)
    movement_count = Column(Integer, default=0)
    penalty_points = Column(Float, default=0)
    window_switches = Column(Integer, default=0)
    browser_info = Column(String(500), nullable=True)
    device_info = Column(String(500), nullable=True)
    ip_address = Column(String(50), nullable=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True), nullable=True)

    student = relationship("User", back_populates="test_results")
    test = relationship("Test", back_populates="results")
    proctor_session = relationship("ProctorSession", back_populates="test_result", uselist=False, cascade="all, delete-orphan")


class ProctorSession(Base):
    __tablename__ = "proctor_sessions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    test_result_id = Column(Integer, ForeignKey("test_results.id"), unique=True)
    session_data = Column(JSON, nullable=True)
    eye_movements = Column(JSON, nullable=True)
    face_movements = Column(JSON, nullable=True)
    window_switches = Column(JSON, nullable=True)
    timestamps = Column(JSON, nullable=True)
    notes = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", back_populates="proctor_sessions")
    test_result = relationship("TestResult", back_populates="proctor_session")


class WrittenSubmission(Base):
    __tablename__ = "written_submissions"

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("users.id"))
    test_id = Column(Integer, ForeignKey("tests.id"))
    answers = Column(JSON, nullable=False)
    anti_plagiarism_data = Column(JSON, nullable=True)
    ai_generated = Column(Boolean, default=False)
    similarity_to_material = Column(Float, default=0.0)
    score = Column(Float, nullable=True)
    max_score = Column(Float, nullable=True)
    feedback = Column(Text, nullable=True)
    graded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    graded_at = Column(DateTime(timezone=True), nullable=True)
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())

    student = relationship("User", foreign_keys=[student_id], back_populates="written_submissions")
    test = relationship("Test", back_populates="written_submissions")
    grader = relationship("User", foreign_keys=[graded_by], back_populates="graded_written")