from __future__ import annotations

from pydantic import BaseModel, Field


class CreateJobRequest(BaseModel):
    domains: list[str] = Field(..., min_length=1)
