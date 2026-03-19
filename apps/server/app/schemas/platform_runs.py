from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ToolRunResponse(BaseModel):
    id: str
    tool_id: str
    status: str
    summary: str
    error_message: str
    created_at: datetime
    updated_at: datetime
