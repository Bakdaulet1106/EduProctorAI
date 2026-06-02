"""
EduProctorAI - Group Management Routes
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime

from .. import models, auth, database
from ..schemas import GroupCreate, GroupUpdate, GroupResponse

router = APIRouter()


@router.get("/", response_model=List[GroupResponse])
async def get_all_groups(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user:
        raise HTTPException(status_code=401, detail="Не авторизован")

    groups = db.query(models.Group).all()
    result = []
    for group in groups:
        student_count = db.query(models.User).filter(
            models.User.role == "student",
            models.User.group_name == group.name
        ).count()
        result.append({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "student_count": student_count,
            "created_at": group.created_at
        })
    return result


@router.get("/teacher-groups", response_model=List[GroupResponse])
async def get_teacher_groups(
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    groups = db.query(models.Group).all()
    result = []
    for group in groups:
        student_count = db.query(models.User).filter(
            models.User.role == "student",
            models.User.group_name == group.name
        ).count()
        result.append({
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "student_count": student_count,
            "created_at": group.created_at
        })
    return result


@router.post("/", response_model=GroupResponse, status_code=201)
async def create_group(
    group: GroupCreate,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    existing = db.query(models.Group).filter(models.Group.name == group.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Группа с таким названием уже существует")

    db_group = models.Group(
        name=group.name,
        description=group.description,
        created_at=datetime.utcnow()
    )
    db.add(db_group)
    db.commit()
    db.refresh(db_group)

    return {
        "id": db_group.id,
        "name": db_group.name,
        "description": db_group.description,
        "student_count": 0,
        "created_at": db_group.created_at
    }


@router.put("/{group_id}", response_model=GroupResponse)
async def update_group(
    group_id: int,
    group: GroupUpdate,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role not in ["admin", "teacher"]:
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    if group.name and group.name != db_group.name:
        existing = db.query(models.Group).filter(models.Group.name == group.name).first()
        if existing:
            raise HTTPException(status_code=400, detail="Такое название группы уже существует")
        db_group.name = group.name

    if group.description is not None:
        db_group.description = group.description

    db.commit()
    db.refresh(db_group)

    student_count = db.query(models.User).filter(
        models.User.role == "student",
        models.User.group_name == db_group.name
    ).count()

    return {
        "id": db_group.id,
        "name": db_group.name,
        "description": db_group.description,
        "student_count": student_count,
        "created_at": db_group.created_at
    }


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    db: Session = Depends(database.get_db),
    token: str = Depends(auth.oauth2_scheme)
):
    current_user = auth.get_current_user(token, db)
    if not current_user or current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Доступ запрещен")

    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not db_group:
        raise HTTPException(status_code=404, detail="Группа не найдена")

    student_count = db.query(models.User).filter(
        models.User.role == "student",
        models.User.group_name == db_group.name
    ).count()

    if student_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"Нельзя удалить группу с {student_count} студентами. Сначала переместите студентов."
        )

    db.delete(db_group)
    db.commit()

    return {"message": "Группа удалена"}