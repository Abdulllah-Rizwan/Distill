"""Workspace — the isolation boundary for one student's data (Principle V)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from distil.domain.errors import DomainError


@dataclass(frozen=True, slots=True)
class Workspace:
    """Container that isolates one student's materials and all derived data.

    v1 has exactly one workspace; it is modelled now so every record can be scoped by
    ``workspace_id`` from the start, keeping the multi-user isolation seam real.
    """

    id: str
    name: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise DomainError("Workspace.name must be non-empty")
