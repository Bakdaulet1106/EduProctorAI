"""
EduProctorAI - Authentication Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime
import logging

from .. import models, auth, database
from ..schemas import UserCreate, UserResponse, Token

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: Session = Depends(database.get_db)):
    existing = db.query(models.User).filter(models.User.iin == user.iin).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пользователь с таким ИИН уже существует"
        )

    if user.role == "student" and user.group_name:
        group = db.query(models.Group).filter(models.Group.name == user.group_name).first()
        if not group:
            group = models.Group(name=user.group_name, created_at=datetime.utcnow())
            db.add(group)
            db.commit()

    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        iin=user.iin,
        password_hash=hashed_password,
        full_name=user.full_name,
        role=user.role,
        group_name=user.group_name if user.role == "student" else None,
        language=user.language,
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    logger.info(f"New user registered: {user.iin} ({user.role})")
    return db_user


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный ИИН или пароль",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = auth.create_access_token(
        data={"sub": user.iin, "user_id": user.id, "role": user.role}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "role": user.role,
        "full_name": user.full_name,
        "iin": user.iin,
        "language": user.language
    }


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    token: str = Depends(auth.oauth2_scheme),
    db: Session = Depends(database.get_db)
):
    user = auth.get_current_user(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Не авторизован"
        )
    return user