"""Pydantic schemas for system endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class SystemInfoOut(BaseModel):
    providers: list[str]
    models: list[str]
    tool_versions: list[str]
    default_provider: str
    default_model: str
    default_tool_version: str
    has_api_key: bool
    base_url: str
    system_prompt_suffix: str
    novnc_url: str


class ApiKeyOut(BaseModel):
    has_key: bool


class ApiKeyIn(BaseModel):
    api_key: str


class BaseUrlOut(BaseModel):
    base_url: str


class BaseUrlIn(BaseModel):
    base_url: str


class SystemPromptOut(BaseModel):
    suffix: str


class SystemPromptIn(BaseModel):
    suffix: str
