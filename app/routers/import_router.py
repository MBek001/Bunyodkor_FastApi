from typing import Annotated
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db import get_db
from app.core.permissions import PERM_STUDENTS_MANAGE
from app.schemas.common import DataResponse
from app.deps import require_permission

router = APIRouter(prefix="/import", tags=["Import"])


@router.post("/students", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_STUDENTS_MANAGE))])
async def import_students(
    file: UploadFile = File(...),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
):
    return DataResponse(
        data={
            "message": "Student import placeholder - implement Excel parsing with openpyxl",
            "filename": file.filename,
        }
    )


@router.get("/students/result", response_model=DataResponse[dict], dependencies=[Depends(require_permission(PERM_STUDENTS_MANAGE))])
async def get_import_result():
    return DataResponse(
        data={
            "message": "Import result placeholder",
            "success_count": 0,
            "error_count": 0,
        }
    )
