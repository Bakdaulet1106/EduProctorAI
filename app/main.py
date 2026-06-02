"""
EduProctorAI - Main FastAPI Application
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import logging
import time
from datetime import datetime

from . import models, database
from .config import settings
from .routes import auth_router, users_router, groups_router, tests_router, exams_router, proctor_router, analytics_router

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/backend.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Intelligent Proctoring System for Distance Learning",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        f"{request.method} {request.url.path} - "
        f"{response.status_code} - "
        f"{duration:.3f}s"
    )
    return response


app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(users_router, prefix=f"{settings.API_V1_STR}/users", tags=["Users"])
app.include_router(groups_router, prefix=f"{settings.API_V1_STR}/groups", tags=["Groups"])
app.include_router(tests_router, prefix=f"{settings.API_V1_STR}/tests", tags=["Tests"])
app.include_router(exams_router, prefix=f"{settings.API_V1_STR}/exams", tags=["Exams"])
app.include_router(proctor_router, prefix=f"{settings.API_V1_STR}/proctor", tags=["Proctoring"])
app.include_router(analytics_router, prefix=f"{settings.API_V1_STR}/analytics", tags=["Analytics"])


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION
    }


@app.get("/")
async def root():
    return {
        "name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "description": "EduProctorAI API Server",
        "documentation": {
            "swagger": "/docs",
            "redoc": "/redoc"
        }
    }


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else None,
            "path": request.url.path
        }
    )


@app.on_event("startup")
async def startup_event():
    logger.info("=" * 70)
    logger.info(f" Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("=" * 70)

    try:
        db = next(database.get_db())
        db.execute(text("SELECT 1"))
        logger.info(" Database connection successful")
        db.close()
    except Exception as e:
        logger.error(f" Database connection failed: {str(e)}")

    logger.info("=" * 70)
    logger.info(" API Documentation: http://localhost:8000/docs")
    logger.info("=" * 70)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("=" * 70)
    logger.info(f" Shutting down {settings.PROJECT_NAME}")
    logger.info("=" * 70)