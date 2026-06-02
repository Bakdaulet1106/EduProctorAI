"""
EduProctorAI - Test Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import json
import logging
import random

from .. import models, auth, database
from ..config import settings
from ..services.test_parser import TestParser
from ..services.umk_parser import UMKParser
from ..utils.helpers import save_upload_file

router = APIRouter()
parser = TestParser()
umk_parser = UMKParser()
logger = logging.getLogger(__name__)


@router.get("/")
async def get_all_tests(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    tests = db.query(models.Test).offset(skip).limit(limit).all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "type": t.type,
            "format": t.format,
            "group_name": t.group_name,
            "question_count": len(t.questions),
            "is_active": t.is_active,
            "created_at": t.created_at
        }
        for t in tests
    ]


@router.get("/recent")
async def get_recent_tests(
    limit: int = 10,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        return []

    query = db.query(models.Test).order_by(models.Test.created_at.desc())
    
    if current_user.role == "teacher":
        query = query.filter(models.Test.created_by == current_user.id)
    
    tests = query.limit(limit).all()
    return [
        {
            "id": t.id,
            "title": t.title,
            "type": t.type,
            "format": t.format,
            "created_at": t.created_at
        }
        for t in tests
    ]


@router.get("/results/recent")
async def get_recent_results(
    limit: int = 10,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        return []

    if current_user.role == "student":
        results = db.query(models.TestResult).filter(
            models.TestResult.student_id == current_user.id
        ).order_by(models.TestResult.completed_at.desc()).limit(limit).all()
    elif current_user.role == "teacher":
        teacher_tests = db.query(models.Test).filter(models.Test.created_by == current_user.id).all()
        test_ids = [t.id for t in teacher_tests]
        results = db.query(models.TestResult).filter(
            models.TestResult.test_id.in_(test_ids)
        ).order_by(models.TestResult.completed_at.desc()).limit(limit).all()
    else:
        results = db.query(models.TestResult).order_by(
            models.TestResult.completed_at.desc()
        ).limit(limit).all()

    response = []
    for r in results:
        student = db.query(models.User).filter(models.User.id == r.student_id).first()
        test = db.query(models.Test).filter(models.Test.id == r.test_id).first()
        response.append({
            "id": r.id,
            "student_id": r.student_id,
            "student_name": student.full_name if student else "Unknown",
            "group_name": student.group_name if student else "Unknown",
            "test_id": r.test_id,
            "test_title": test.title if test else "Unknown",
            "test_type": test.type if test else "unknown",
            "score": r.score,
            "max_score": r.max_score,
            "percentage": r.percentage,
            "letter_grade": r.letter_grade,
            "gpa": r.gpa,
            "movement_count": r.movement_count,
            "penalty_points": r.penalty_points,
            "completed_at": r.completed_at,
            "answers": r.answers
        })
    return response


@router.get("/available/{group_name}")
async def get_available_tests(
    group_name: str,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    tests = db.query(models.Test).filter(
        models.Test.group_name == group_name,
        models.Test.is_active == True
    ).all()

    result = []
    for test in tests:
        if current_user.role == "student":
            if test.assigned_students and current_user.id not in test.assigned_students:
                continue
            if test.format == "test":
                existing = db.query(models.TestResult).filter(
                    models.TestResult.student_id == current_user.id,
                    models.TestResult.test_id == test.id,
                    models.TestResult.completed_at.isnot(None)
                ).first()
                if existing:
                    continue
            elif test.format == "written":
                written_exists = db.query(models.WrittenSubmission).filter(
                    models.WrittenSubmission.student_id == current_user.id,
                    models.WrittenSubmission.test_id == test.id
                ).first()
                if written_exists:
                    continue

        result.append({
            "id": test.id,
            "title": test.title,
            "type": test.type,
            "format": test.format,
            "max_score": test.max_score,
            "time_limit_minutes": test.time_limit_minutes,
            "question_count": len(test.questions),
            "created_at": test.created_at
        })

    return result


@router.get("/{test_id}")
async def get_test(
    test_id: int,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if current_user.role == "student":
        if test.group_name and test.group_name != current_user.group_name:
            raise HTTPException(status_code=403, detail="Access denied")
        if test.assigned_students and current_user.id not in test.assigned_students:
            raise HTTPException(status_code=403, detail="Access denied")

    return test


@router.post("/import/umk")
async def import_umk_material(
    file: UploadFile = File(...),
    title: str = Form(...),
    subject: str = Form(None),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    content = await file.read()
    text = parser.extract_text(content, file.filename)

    if not text:
        raise HTTPException(status_code=400, detail="Could not extract text from file")

    parsed_data = umk_parser.parse_umk(text)
    
    file_path = await save_upload_file(file, f"umk_{title}")
    
    material = models.EducationalMaterial(
        title=title,
        subject=subject,
        file_path=file_path,
        extracted_text=text[:10000],
        rk1_questions=parsed_data.get('rk1_questions', []),
        rk2_questions=parsed_data.get('rk2_questions', []),
        final_questions=parsed_data.get('final_questions', []),
        lecture_texts=parsed_data.get('lecture_texts', []),
        created_by=current_user.id,
        created_at=datetime.utcnow()
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    return {
        "message": "Educational material imported successfully",
        "material_id": material.id,
        "title": title,
        "rk1_questions": len(parsed_data.get('rk1_questions', [])),
        "rk2_questions": len(parsed_data.get('rk2_questions', [])),
        "final_questions": len(parsed_data.get('final_questions', [])),
        "lectures_count": len(parsed_data.get('lecture_texts', []))
    }


@router.post("/generate/written")
async def generate_written_from_umk(
    material_id: int = Form(...),
    test_type: str = Form(...),
    group_name: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    language: str = Form("en"),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    material = db.query(models.EducationalMaterial).filter(
        models.EducationalMaterial.id == material_id
    ).first()

    if not material:
        raise HTTPException(status_code=404, detail="Educational material not found")

    if test_type == 'rk1':
        questions_list = material.rk1_questions or []
    elif test_type == 'rk2':
        questions_list = material.rk2_questions or []
    else:
        questions_list = material.final_questions or []
        if not questions_list:
            questions_list = (material.rk1_questions or []) + (material.rk2_questions or [])
            questions_list = questions_list[:5]

    if not questions_list:
        raise HTTPException(status_code=400, detail="No questions found in the material for this test type")

    if test_type == 'exam':
        num_questions = 5
    else:
        num_questions = 3

    selected_questions = random.sample(questions_list, min(num_questions, len(questions_list)))
    
    lecture_texts = material.lecture_texts or []
    
    formatted_questions = []
    for i, q in enumerate(selected_questions):
        q_text = q.get('text', '') if isinstance(q, dict) else q
        reference_answer = umk_parser.find_answer_in_lectures(q_text, lecture_texts)
        
        formatted_questions.append({
            'id': i + 1,
            'text': q_text,
            'max_score': 10,
            'type': 'written',
            'ai_generated': True,
            'reference_answer': reference_answer,
            'keywords': umk_parser._extract_keywords(q_text)
        })

    time_limits = {"rk1": 60, "rk2": 60, "exam": 90}
    time_limit = time_limits.get(test_type, 60)
    
    test = models.Test(
        title=title or f"Written {test_type.upper()} - {group_name}",
        type=test_type,
        format="written",
        description=description,
        questions=formatted_questions,
        max_score=100,
        time_limit_minutes=time_limit,
        passing_score=50,
        max_attempts=1,
        created_by=current_user.id,
        source_material_id=material_id,
        group_name=group_name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    return {
        "message": "Written questions generated successfully from educational material",
        "test_id": test.id,
        "questions": formatted_questions,
        "questions_count": len(formatted_questions),
        "source_material": material.title
    }


@router.post("/import/rk1")
async def import_rk1(
    file: UploadFile = File(...),
    group_name: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    content = await file.read()
    questions = parser.parse_test(content, file.filename)

    if not questions:
        raise HTTPException(status_code=400, detail="No questions found in file")

    simple = sum(1 for q in questions if q['difficulty'] == 'simple')
    medium = sum(1 for q in questions if q['difficulty'] == 'medium')
    hard = sum(1 for q in questions if q['difficulty'] == 'hard')
    total = len(questions)

    if total < 20:
        raise HTTPException(status_code=400, detail=f"РК1 requires minimum 20 questions (found {total})")

    test = models.Test(
        title=title or f"РК1 - {group_name}",
        type="rk1",
        format="test",
        description=description,
        questions=questions,
        max_score=100,
        time_limit_minutes=35,
        passing_score=50,
        max_attempts=2,
        created_by=current_user.id,
        group_name=group_name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    await save_upload_file(file, f"rk1_{test.id}")

    return {
        "message": f"РК1 imported successfully",
        "test_id": test.id,
        "questions_count": total,
        "simple_count": simple,
        "medium_count": medium,
        "hard_count": hard
    }


@router.post("/import/rk2")
async def import_rk2(
    file: UploadFile = File(...),
    group_name: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    content = await file.read()
    questions = parser.parse_test(content, file.filename)

    if not questions:
        raise HTTPException(status_code=400, detail="No questions found in file")

    simple = sum(1 for q in questions if q['difficulty'] == 'simple')
    medium = sum(1 for q in questions if q['difficulty'] == 'medium')
    hard = sum(1 for q in questions if q['difficulty'] == 'hard')
    total = len(questions)

    if total < 20:
        raise HTTPException(status_code=400, detail=f"РК2 requires minimum 20 questions (found {total})")

    test = models.Test(
        title=title or f"РК2 - {group_name}",
        type="rk2",
        format="test",
        description=description,
        questions=questions,
        max_score=100,
        time_limit_minutes=35,
        passing_score=50,
        max_attempts=2,
        created_by=current_user.id,
        group_name=group_name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    await save_upload_file(file, f"rk2_{test.id}")

    return {
        "message": f"РК2 imported successfully",
        "test_id": test.id,
        "questions_count": total,
        "simple_count": simple,
        "medium_count": medium,
        "hard_count": hard
    }


@router.post("/import/exam")
async def import_exam(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...),
    group_name: str = Form(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    content1 = await file1.read()
    content2 = await file2.read()
    questions_rk1 = parser.parse_test(content1, file1.filename)
    questions_rk2 = parser.parse_test(content2, file2.filename)

    if not questions_rk1 or not questions_rk2:
        raise HTTPException(status_code=400, detail="Could not parse both files")

    exam_questions = parser.prepare_exam_questions(questions_rk1, questions_rk2)

    if len(exam_questions) != 50:
        raise HTTPException(status_code=400, detail=f"Exam requires 50 questions (got {len(exam_questions)})")

    test = models.Test(
        title=title or f"Exam - {group_name}",
        type="exam",
        format="test",
        description=description,
        questions=exam_questions,
        max_score=100,
        time_limit_minutes=80,
        passing_score=50,
        max_attempts=1,
        created_by=current_user.id,
        group_name=group_name,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(test)
    db.commit()
    db.refresh(test)

    await save_upload_file(file1, f"exam_{test.id}_rk1")
    await save_upload_file(file2, f"exam_{test.id}_rk2")

    return {
        "message": "Exam imported successfully",
        "test_id": test.id,
        "questions_count": len(exam_questions)
    }


@router.post("/assign")
async def assign_test(
    test_id: int = Form(...),
    group_name: str = Form(...),
    assign_to_all: bool = Form(False),
    student_ids: Optional[str] = Form(None),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if assign_to_all:
        test.assigned_students = None
        test.group_name = group_name
    else:
        ids = json.loads(student_ids) if student_ids else []
        test.assigned_students = ids
        test.group_name = group_name

    db.commit()

    return {"message": "Test assigned successfully"}


@router.get("/teacher/materials")
async def get_teacher_materials(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    materials = db.query(models.EducationalMaterial).filter(
        models.EducationalMaterial.created_by == current_user.id
    ).all()

    return [
        {
            "id": m.id,
            "title": m.title,
            "subject": m.subject,
            "created_at": m.created_at,
            "rk1_count": len(m.rk1_questions or []),
            "rk2_count": len(m.rk2_questions or []),
            "final_count": len(m.final_questions or [])
        }
        for m in materials
    ]