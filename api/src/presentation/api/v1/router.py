"""Presentation — Main API v1 router aggregator."""
from fastapi import APIRouter

from src.presentation.api.v1.auth.router import router as auth_router
from src.presentation.api.v1.documents.router import router as documents_router
from src.presentation.api.v1.documents.upload_dev_router import router as upload_dev_router
from src.presentation.api.v1.legacy.router import router as legacy_router
from src.presentation.api.v1.users_audit_routers import audit_router, users_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(upload_dev_router)   # ← Upload sem auth (DEV only)
api_v1_router.include_router(legacy_router)        # ← GED Legado Oracle/Gemmius
api_v1_router.include_router(users_router)
api_v1_router.include_router(audit_router)
