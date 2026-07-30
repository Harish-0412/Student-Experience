from fastapi import APIRouter

from astrapath.api.routes import admin, auth, health, student

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(student.router, prefix="/student", tags=["Student"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])

