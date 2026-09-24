from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_user
from app.db import get_db
from app.models import Category, User
from app.schemas.category import CategoryOut

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_db),
) -> list[CategoryOut]:
    """All categories, including inactive ones, so existing tickets can still
    show their category's name."""
    rows = await session.scalars(select(Category).order_by(Category.id))
    return [CategoryOut.model_validate(c) for c in rows]
