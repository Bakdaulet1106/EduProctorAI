"""
EduProctorAI - User Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime

from .. import models, auth, database
from ..schemas import UserResponse, UserUpdate
from ..utils.helpers import calculate_gpa

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    users = db.query(models.User).offset(skip).limit(limit).all()
    return users


@router.get("/students/{group_name}")
async def get_students_by_group(
    group_name: str,
    sort_by: str = Query("name", pattern="^(name|iin|score|movements|gpa)$"),
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    if current_user.role not in ["admin", "teacher"] and current_user.group_name != group_name:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    students = db.query(models.User).filter(
        models.User.role == "student",
        models.User.group_name == group_name
    ).all()

    result = []
    for student in students:
        results = db.query(models.TestResult).filter(
            models.TestResult.student_id == student.id
        ).all()

        total_tests = len(results)
        avg_score = sum(r.percentage for r in results) / total_tests if total_tests > 0 else 0
        total_movements = sum(r.movement_count for r in results)

        results_for_gpa = []
        for r in results:
            test = db.query(models.Test).filter(models.Test.id == r.test_id).first()
            results_for_gpa.append({"percentage": r.percentage, "test_type": test.type if test else "test"})
        gpa = calculate_gpa(results_for_gpa)

        last_active = max((r.completed_at for r in results if r.completed_at), default=None)

        result.append({
            "id": student.id,
            "iin": student.iin,
            "full_name": student.full_name,
            "group_name": student.group_name,
            "total_tests": total_tests,
            "average_score": round(avg_score, 1),
            "gpa": gpa,
            "total_movements": total_movements,
            "last_active": last_active
        })

    if sort_by == "name":
        result.sort(key=lambda x: x["full_name"])
    elif sort_by == "score":
        result.sort(key=lambda x: x["average_score"], reverse=True)
    elif sort_by == "movements":
        result.sort(key=lambda x: x["total_movements"], reverse=True)
    elif sort_by == "gpa":
        result.sort(key=lambda x: x["gpa"], reverse=True)

    return result


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    if current_user.role not in ["admin", "teacher"] and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    return user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    update_data = user_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)

    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить самого себя")

    db.delete(user)
    db.commit()

    return {"message": "Пользователь удален"}