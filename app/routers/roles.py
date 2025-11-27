from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.db import get_db
from app.core.permissions import PERM_ROLES_MANAGE, ALL_PERMISSIONS
from app.models.auth import Role, Permission
from app.schemas.auth import RoleRead, RoleCreate, RoleUpdate, RoleWithPermissions, PermissionRead
from app.schemas.common import DataResponse
from app.deps import require_permission

router = APIRouter(prefix="/roles", tags=["Roles"])


@router.get("", response_model=DataResponse[list[RoleWithPermissions]], dependencies=[Depends(require_permission(PERM_ROLES_MANAGE))])
async def get_roles(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return DataResponse(data=[RoleWithPermissions.model_validate(r) for r in roles])


@router.post("", response_model=DataResponse[RoleWithPermissions], dependencies=[Depends(require_permission(PERM_ROLES_MANAGE))])
async def create_role(
    data: RoleCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    role = Role(name=data.name, description=data.description)

    if data.permission_ids:
        perms_result = await db.execute(select(Permission).where(Permission.id.in_(data.permission_ids)))
        permissions = perms_result.scalars().all()
        role.permissions = permissions

    db.add(role)
    await db.commit()
    await db.refresh(role)

    return DataResponse(data=RoleWithPermissions.model_validate(role))


@router.patch("/{role_id}", response_model=DataResponse[RoleWithPermissions], dependencies=[Depends(require_permission(PERM_ROLES_MANAGE))])
async def update_role(
    role_id: int,
    data: RoleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalar_one_or_none()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if data.name:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permission_ids is not None:
        perms_result = await db.execute(select(Permission).where(Permission.id.in_(data.permission_ids)))
        permissions = perms_result.scalars().all()
        role.permissions = permissions

    await db.commit()
    await db.refresh(role)

    return DataResponse(data=RoleWithPermissions.model_validate(role))


@router.get("/permissions", response_model=DataResponse[list[PermissionRead]])
async def get_permissions(db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(Permission))
    permissions = result.scalars().all()
    return DataResponse(data=[PermissionRead.model_validate(p) for p in permissions])
