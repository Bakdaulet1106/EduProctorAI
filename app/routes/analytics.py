"""
EduProctorAI - Analytics Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta

from .. import models, auth, database
from ..utils.helpers import calculate_gpa

router = APIRouter()


@router.get("/stats")
async def get_stats(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    student_count = db.query(models.User).filter(models.User.role == "student").count()
    group_count = db.query(models.Group).count()
    test_count = db.query(models.Test).filter(models.Test.is_active == True).count()
    avg_score = db.query(func.avg(models.TestResult.percentage)).scalar() or 0
    total_movements = db.query(func.sum(models.TestResult.movement_count)).scalar() or 0

    return {
        "studentCount": student_count,
        "groupCount": group_count,
        "testCount": test_count,
        "averageScore": round(avg_score, 1),
        "totalMovements": total_movements
    }


@router.get("/student-stats")
async def get_student_stats(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "student":
        raise HTTPException(status_code=403, detail="Access denied")

    results = db.query(models.TestResult).filter(
        models.TestResult.student_id == current_user.id
    ).all()

    total_tests = len(results)
    avg_score = sum(r.percentage for r in results) / total_tests if total_tests > 0 else 0
    total_movements = sum(r.movement_count for r in results)
    best_score = max([r.percentage for r in results], default=0)

    results_for_gpa = []
    for r in results:
        test = db.query(models.Test).filter(models.Test.id == r.test_id).first()
        results_for_gpa.append({
            "percentage": r.percentage,
            "test_type": test.type if test else "test"
        })
    gpa = calculate_gpa(results_for_gpa)

    return {
        "totalTests": total_tests,
        "averageScore": round(avg_score, 1),
        "totalMovements": total_movements,
        "gpa": gpa,
        "bestScore": round(best_score, 1)
    }


@router.get("/teacher-stats")
async def get_teacher_stats(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    tests = db.query(models.Test).filter(models.Test.created_by == current_user.id).all()
    test_ids = [t.id for t in tests]

    student_count = db.query(models.User).filter(models.User.role == "student").count()
    test_count = len(tests)

    results = db.query(models.TestResult).filter(models.TestResult.test_id.in_(test_ids)).all()
    avg_score = sum(r.percentage for r in results) / len(results) if results else 0
    total_movements = sum(r.movement_count for r in results)

    return {
        "studentCount": student_count,
        "testCount": test_count,
        "averageScore": round(avg_score, 1),
        "totalMovements": total_movements
    }


@router.get("/groups-performance")
async def get_groups_performance(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    groups = db.query(models.Group).all()
    result = []

    for group in groups:
        students = db.query(models.User).filter(
            models.User.role == "student",
            models.User.group_name == group.name
        ).all()

        student_ids = [s.id for s in students]
        results = db.query(models.TestResult).filter(
            models.TestResult.student_id.in_(student_ids)
        ).all()

        total_tests = len(results)
        avg_score = sum(r.percentage for r in results) / total_tests if total_tests > 0 else 0
        passed = len([r for r in results if r.percentage >= 50])
        total_movements = sum(r.movement_count for r in results)

        result.append({
            "name": group.name,
            "students": len(students),
            "tests": total_tests,
            "average": round(avg_score, 1),
            "passRate": round((passed / total_tests * 100) if total_tests > 0 else 0, 1),
            "totalMovements": total_movements,
            "avgMovements": round(total_movements / total_tests, 1) if total_tests > 0 else 0
        })

    return result


@router.get("/activity")
async def get_activity(
    period: str = Query("month"),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    days = 7 if period == "week" else 30
    start_date = datetime.utcnow() - timedelta(days=days)

    results = db.query(models.TestResult).filter(
        models.TestResult.completed_at >= start_date
    ).all()

    daily = {}
    for r in results:
        if r.completed_at:
            date_str = r.completed_at.date().isoformat()
            if date_str not in daily:
                daily[date_str] = {"tests": 0, "scores": 0}
            daily[date_str]["tests"] += 1
            daily[date_str]["scores"] += r.percentage

    labels = sorted(daily.keys())
    tests_data = [daily[d]["tests"] for d in labels]
    scores_data = [round(daily[d]["scores"] / daily[d]["tests"], 1) if daily[d]["tests"] > 0 else 0 for d in labels]

    return {"labels": labels, "tests": tests_data, "scores": scores_data}


@router.get("/groups-distribution")
async def get_groups_distribution(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    groups = db.query(models.Group).all()
    labels, values = [], []

    for group in groups:
        count = db.query(models.User).filter(
            models.User.role == "student",
            models.User.group_name == group.name
        ).count()
        if count > 0:
            labels.append(group.name)
            values.append(count)

    return {"labels": labels, "values": values}


@router.get("/teacher-trends")
async def get_teacher_trends(
    period: str = Query("week"),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")

    days = 7 if period == "week" else 30
    start_date = datetime.utcnow() - timedelta(days=days)

    tests = db.query(models.Test).filter(models.Test.created_by == current_user.id).all()
    test_ids = [t.id for t in tests]

    results = db.query(models.TestResult).filter(
        models.TestResult.test_id.in_(test_ids),
        models.TestResult.completed_at >= start_date
    ).all()

    daily = {}
    for r in results:
        if r.completed_at:
            date_str = r.completed_at.date().isoformat()
            if date_str not in daily:
                daily[date_str] = {"tests": 0, "scores": 0}
            daily[date_str]["tests"] += 1
            daily[date_str]["scores"] += r.percentage

    labels = sorted(daily.keys())
    tests_data = [daily[d]["tests"] for d in labels]
    scores_data = [round(daily[d]["scores"] / daily[d]["tests"], 1) if daily[d]["tests"] > 0 else 0 for d in labels]

    return {"labels": labels, "tests": tests_data, "scores": scores_data}