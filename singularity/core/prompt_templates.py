"""
Singularity — Prompt Template Registry (Fáze 21).

Named, versioned prompt templates with {{variable}} substitution.
Multiple registrations under the same name bump the version automatically.
Fully offline — no external dependencies.
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import structlog

log = structlog.get_logger()

_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")


def _extract_variables(template: str) -> list[str]:
    """Return deduplicated list of {{variable}} names found in template."""
    seen: dict[str, None] = {}
    for m in _VAR_PATTERN.finditer(template):
        seen[m.group(1)] = None
    return list(seen)


@dataclass
class PromptTemplate:
    template_id: str
    name: str
    version: int
    template: str
    description: str
    tags: list[str]
    variables: list[str]
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def render(self, **kwargs: Any) -> str:
        missing = [v for v in self.variables if v not in kwargs]
        if missing:
            raise ValueError(f"Missing template variables: {missing}")
        result = self.template
        for k, v in kwargs.items():
            result = result.replace("{{" + k + "}}", str(v))
        return result

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "version": self.version,
            "template": self.template,
            "description": self.description,
            "tags": self.tags,
            "variables": self.variables,
            "created_at": self.created_at,
        }


class PromptTemplateRegistry:
    """
    Thread-safe registry for named, versioned prompt templates.

    Usage:
        tid = reg.register("summarise", "Summarise {{text}} in {{lang}}.")
        output = reg.render(tid, text="Hello world", lang="Czech")
    """

    def __init__(self) -> None:
        self._templates: dict[str, PromptTemplate] = {}
        self._versions: dict[str, int] = {}  # name → latest version number
        self._lock = threading.Lock()

    def register(
        self,
        name: str,
        template: str,
        description: str = "",
        tags: list[str] | None = None,
    ) -> str:
        """Register a template. Re-registering the same name bumps the version."""
        if not name or not name.strip():
            raise ValueError("name must not be empty")
        if not template:
            raise ValueError("template must not be empty")
        variables = _extract_variables(template)
        template_id = str(uuid.uuid4())
        with self._lock:
            version = self._versions.get(name, 0) + 1
            self._versions[name] = version
            self._templates[template_id] = PromptTemplate(
                template_id=template_id,
                name=name,
                version=version,
                template=template,
                description=description,
                tags=list(tags or []),
                variables=variables,
            )
        log.info("prompt_template_registered", template_id=template_id,
                 name=name, version=version, variables=variables)
        return template_id

    def get(self, template_id: str) -> dict | None:
        with self._lock:
            t = self._templates.get(template_id)
        return t.to_dict() if t else None

    def get_by_name(self, name: str) -> list[dict]:
        """Return all versions of a template, newest first."""
        with self._lock:
            items = [t for t in self._templates.values() if t.name == name]
        return [t.to_dict() for t in sorted(items, key=lambda t: t.version, reverse=True)]

    def get_latest(self, name: str) -> dict | None:
        """Return the latest version of a named template."""
        versions = self.get_by_name(name)
        return versions[0] if versions else None

    def list_templates(self, tag: str | None = None) -> list[dict]:
        with self._lock:
            items = list(self._templates.values())
        if tag is not None:
            items = [t for t in items if tag in t.tags]
        return [t.to_dict() for t in items]

    def delete(self, template_id: str) -> bool:
        with self._lock:
            if template_id not in self._templates:
                return False
            del self._templates[template_id]
        return True

    def render(self, template_id: str, **kwargs: Any) -> str:
        """Render a template by id, substituting {{variables}} from kwargs."""
        with self._lock:
            t = self._templates.get(template_id)
        if t is None:
            raise KeyError(f"No template: {template_id!r}")
        return t.render(**kwargs)

    def template_count(self) -> int:
        with self._lock:
            return len(self._templates)
