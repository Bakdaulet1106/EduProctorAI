"""
EduProctorAI - Exam Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from .. import models, auth, database
from ..utils.helpers import calculate_test_score, percentage_to_gpa, get_letter_grade
from ..utils.anti_plagiarism import AntiPlagiarism

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/start/{test_id}")
async def start_exam(
    test_id: int,
    request: Request,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "student":
        raise HTTPException(status_code=403, detail="Access denied")

    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    if test.group_name and test.group_name != current_user.group_name:
        raise HTTPException(status_code=403, detail="This test is not for your group")

    if not test.is_active:
        raise HTTPException(status_code=400, detail="Test is not active")

    attempts_count = db.query(models.TestResult).filter(
        models.TestResult.student_id == current_user.id,
        models.TestResult.test_id == test_id,
        models.TestResult.completed_at.isnot(None)
    ).count()

    if attempts_count >= test.max_attempts:
        raise HTTPException(status_code=400, detail="You have exceeded the number of attempts")

    existing = db.query(models.TestResult).filter(
        models.TestResult.student_id == current_user.id,
        models.TestResult.test_id == test_id,
        models.TestResult.completed_at.is_(None)
    ).first()

    if existing:
        return {
            "exam_id": existing.id,
            "test_id": test.id,
            "title": test.title,
            "type": test.type,
            "format": test.format,
            "questions": test.questions,
            "time_limit_minutes": test.time_limit_minutes,
            "max_score": test.max_score,
            "started_at": existing.started_at
        }

    test_result = models.TestResult(
        student_id=current_user.id,
        test_id=test_id,
        score=0,
        max_score=test.max_score,
        percentage=0,
        started_at=datetime.utcnow(),
        ip_address=request.client.host if request.client else None,
        browser_info=request.headers.get("user-agent", "")[:500],
        device_info=request.headers.get("sec-ch-ua-platform", "Unknown")[:500]
    )
    db.add(test_result)
    db.commit()
    db.refresh(test_result)

    return {
        "exam_id": test_result.id,
        "test_id": test.id,
        "title": test.title,
        "type": test.type,
        "format": test.format,
        "questions": test.questions,
        "time_limit_minutes": test.time_limit_minutes,
        "max_score": test.max_score,
        "started_at": test_result.started_at
    }


@router.post("/submit/{exam_id}")
async def submit_exam(
    exam_id: int,
    submission: dict,
    request: Request,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "student":
        raise HTTPException(status_code=403, detail="Access denied")

    test_result = db.query(models.TestResult).filter(
        models.TestResult.id == exam_id,
        models.TestResult.student_id == current_user.id
    ).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test not found")

    if test_result.completed_at:
        raise HTTPException(status_code=400, detail="Test already submitted")

    test = db.query(models.Test).filter(models.Test.id == test_result.test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    answers = submission.get("answers", {})
    
    if test.format == "test":
        score_result = calculate_test_score(test, answers)
    else:
        score_result = {"score": 0, "max_score": test.max_score}
        
        reference_answers = {}
        for q in test.questions:
            if 'reference_answer' in q:
                reference_answers[q['id']] = q['reference_answer']
        
        total_score = 0
        for q_id, ans in answers.items():
            ref_ans = reference_answers.get(q_id, '')
            if ref_ans:
                check = AntiPlagiarism.check_against_reference(ans, ref_ans)
                total_score += check['similarity'] * 10
        
        score_result["score"] = total_score

    movement_count = submission.get("proctor_data", {}).get("movementCount", 0)
    window_switches = submission.get("proctor_data", {}).get("windowSwitches", 0)
    
    penalty = min(movement_count * 1.0 + window_switches * 2.0, 30.0)
    final_score = max(0, score_result["score"] - penalty)
    final_percentage = (final_score / score_result["max_score"]) * 100 if score_result["max_score"] > 0 else 0

    gpa = percentage_to_gpa(final_percentage)
    letter_grade = get_letter_grade(final_percentage)

    test_result.score = final_score
    test_result.percentage = final_percentage
    test_result.gpa = gpa
    test_result.letter_grade = letter_grade
    test_result.answers = answers
    test_result.proctor_notes = submission.get("proctor_data", {})
    test_result.movement_count = movement_count
    test_result.window_switches = window_switches
    test_result.penalty_points = penalty
    test_result.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(test_result)

    return {
        "result_id": test_result.id,
        "score": final_score,
        "max_score": score_result["max_score"],
        "percentage": final_percentage,
        "letter_grade": letter_grade,
        "gpa": gpa,
        "movement_count": movement_count,
        "window_switches": window_switches,
        "penalty_points": penalty
    }


@router.post("/submit/written")
async def submit_written_exam(
    submission: dict,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "student":
        raise HTTPException(status_code=403, detail="Access denied")

    test_id = submission.get("test_id")
    answers = submission.get("answers", {})

    test = db.query(models.Test).filter(models.Test.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    existing = db.query(models.WrittenSubmission).filter(
        models.WrittenSubmission.student_id == current_user.id,
        models.WrittenSubmission.test_id == test_id
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="You have already submitted this exam")

    reference_answers = {}
    for q in test.questions:
        if 'reference_answer' in q:
            reference_answers[q['id']] = q['reference_answer']
    
    plagiarism_report = AntiPlagiarism.full_report(answers, reference_answers, [])
    
    total_score = 0
    for q_id, ans in answers.items():
        ref_ans = reference_answers.get(q_id, '')
        if ref_ans:
            check = AntiPlagiarism.check_against_reference(ans, ref_ans)
            total_score += check['similarity'] * 10

    written = models.WrittenSubmission(
        student_id=current_user.id,
        test_id=test_id,
        answers=answers,
        anti_plagiarism_data=plagiarism_report,
        similarity_to_material=plagiarism_report.get('average_similarity', 0),
        score=total_score,
        max_score=len(test.questions) * 10,
        submitted_at=datetime.utcnow()
    )
    db.add(written)
    db.commit()
    db.refresh(written)

    return {
        "id": written.id,
        "score": total_score,
        "max_score": written.max_score,
        "percentage": (total_score / written.max_score) * 100 if written.max_score > 0 else 0,
        "plagiarism_report": plagiarism_report,
        "submitted_at": written.submitted_at
    }


@router.get("/results/{group_name}")
async def get_group_exam_results(
    group_name: str,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Access denied")

    students = db.query(models.User).filter(
        models.User.role == "student",
        models.User.group_name == group_name
    ).all()

    results = []
    for student in students:
        test_results = db.query(models.TestResult).filter(
            models.TestResult.student_id == student.id
        ).order_by(models.TestResult.completed_at.desc()).all()

        for result in test_results:
            test = db.query(models.Test).filter(models.Test.id == result.test_id).first()
            if current_user.role == "teacher" and test and test.created_by != current_user.id:
                continue

            results.append({
                "id": result.id,
                "student_id": student.id,
                "student_name": student.full_name,
                "student_iin": student.iin,
                "group_name": student.group_name,
                "test_id": result.test_id,
                "test_title": test.title if test else "Unknown",
                "test_type": test.type if test else "unknown",
                "score": result.score,
                "max_score": result.max_score,
                "percentage": result.percentage,
                "letter_grade": result.letter_grade,
                "gpa": result.gpa,
                "movement_count": result.movement_count,
                "window_switches": result.window_switches,
                "penalty_points": result.penalty_points,
                "completed_at": result.completed_at.isoformat() if result.completed_at else None,
                "answers": result.answers
            })

    return results