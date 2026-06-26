"""Evidence file serving."""

import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.config import get_settings
from app.core.dependencies import get_current_user
from app.models import User

router = APIRouter(prefix="/evidence", tags=["Evidence"])
settings = get_settings()


@router.get("/snapshots/{filename}")
async def get_snapshot(filename: str, current_user: User = Depends(get_current_user)):
    filepath = os.path.join(settings.snapshots_path, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Snapshot no encontrado")
    return FileResponse(filepath, media_type="image/jpeg")
