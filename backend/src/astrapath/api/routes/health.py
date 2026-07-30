from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from astrapath import __version__
from astrapath.db import get_db
from astrapath.schemas import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    return HealthResponse(status="ok", service="astrapath-api", version=__version__)


@router.get("/health/ready", response_model=HealthResponse)
def readiness(db: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    db.execute(text("SELECT 1"))
    return HealthResponse(status="ready", service="astrapath-api", version=__version__)

