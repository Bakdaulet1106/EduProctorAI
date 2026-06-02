"""
EduProctorAI - Authentication and Authorization
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
import bcrypt
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import logging

from . import models
from .config import settings

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False
)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception as e:
        logger.error(f"Password verification error: {str(e)}")
        return False


def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def authenticate_user(db: Session, iin: str, password: str) -> Optional[models.User]:
    try:
        user = db.query(models.User).filter(models.User.iin == iin).first()
        if not user:
            logger.warning(f"Authentication failed: User not found - IIN: {iin}")
            return None
        if not verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: Invalid password - IIN: {iin}")
            return None
        if not user.is_active:
            logger.warning(f"Authentication failed: User inactive - IIN: {iin}")
            return None

        user.last_login = datetime.utcnow()
        db.commit()
        
        logger.info(f"User authenticated: {user.iin} ({user.role})")
        return user
    except Exception as e:
        logger.error(f"Authentication error: {str(e)}")
        return None


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow(),
        "type": "access"
    })
    try:
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    except Exception as e:
        logger.error(f"Token creation error: {str(e)}")
        raise


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        logger.warning(f"Token decode error: {str(e)}")
        return None


def get_current_user(token: str, db: Session) -> Optional[models.User]:
    if not token:
        return None
    
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    
    user_id = payload.get("user_id")
    if not user_id:
        return None
    
    try:
        return db.query(models.User).filter(models.User.id == user_id).first()
    except Exception as e:
        logger.error(f"Error getting current user: {str(e)}")
        return None