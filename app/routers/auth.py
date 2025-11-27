from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.core.db import get_db
from app.core.security import verify_password, create_access_token, hash_password
from app.models.auth import User
from app.schemas.auth import LoginRequest, TokenResponse, CurrentUserResponse, UserWithRoles, PermissionRead
from app.deps import CurrentUser

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(User).where(
            (User.phone == credentials.phone_or_email) | (User.email == credentials.phone_or_email)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone/email or password",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(user: CurrentUser, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.roles).selectinload(User.roles.property.mapper.class_.permissions)
        )
        .where(User.id == user.id)
    )
    user_with_relations = result.scalar_one()

    permissions = []
    if user.is_super_admin:
        from app.core.permissions import ALL_PERMISSIONS
        permissions = [p["code"] for p in ALL_PERMISSIONS]
    else:
        permission_set = set()
        for role in user_with_relations.roles:
            for perm in role.permissions:
                permission_set.add(perm.code)
        permissions = list(permission_set)

    return CurrentUserResponse(
        user=UserWithRoles.model_validate(user_with_relations),
        permissions=permissions,
    )
