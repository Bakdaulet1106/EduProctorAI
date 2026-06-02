from .auth import router as auth_router
from .users import router as users_router
from .groups import router as groups_router
from .tests import router as tests_router
from .exams import router as exams_router
from .proctor import router as proctor_router
from .analytics import router as analytics_router

__all__ = [
    'auth_router',
    'users_router',
    'groups_router',
    'tests_router',
    'exams_router',
    'proctor_router',
    'analytics_router'
]