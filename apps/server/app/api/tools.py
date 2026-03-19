from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models import User
from app.tools.registry import list_tool_manifests, list_tool_routers


router = APIRouter(tags=["tools"])


@router.get("/tools")
def list_tools(user: User = Depends(get_current_user)) -> list[dict]:
    return list_tool_manifests()


for tool_router in list_tool_routers():
    router.include_router(tool_router)
