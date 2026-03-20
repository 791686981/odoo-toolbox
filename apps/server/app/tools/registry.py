from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from fastapi import APIRouter

from app.tools.csv_translation.manifest import TOOL_MANIFEST as CSV_TRANSLATION_TOOL_MANIFEST
from app.tools.csv_translation.router import router as csv_translation_router
from app.tools.gettext_translation.manifest import TOOL_MANIFEST as GETTEXT_TRANSLATION_TOOL_MANIFEST
from app.tools.gettext_translation.router import router as gettext_translation_router


@dataclass(frozen=True)
class ToolRegistration:
    manifest: dict
    router: APIRouter | None = None


REGISTERED_TOOLS = [
    ToolRegistration(
        manifest=CSV_TRANSLATION_TOOL_MANIFEST,
        router=csv_translation_router,
    ),
    ToolRegistration(
        manifest=GETTEXT_TRANSLATION_TOOL_MANIFEST,
        router=gettext_translation_router,
    ),
]


def list_tool_manifests() -> list[dict]:
    return [
        deepcopy(registration.manifest)
        for registration in sorted(REGISTERED_TOOLS, key=lambda item: item.manifest["order"])
        if registration.manifest.get("enabled", False)
    ]


def list_tool_routers() -> list[APIRouter]:
    return [
        registration.router
        for registration in sorted(REGISTERED_TOOLS, key=lambda item: item.manifest["order"])
        if registration.manifest.get("enabled", False) and registration.router is not None
    ]
