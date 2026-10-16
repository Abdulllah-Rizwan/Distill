"""Domain-level exceptions.

Raised when a domain invariant is violated. Kept separate from framework/HTTP concerns so the
core stays pure (hexagonal architecture).
"""

from __future__ import annotations


class DomainError(Exception):
    """Base class for all domain invariant violations."""


class ProvenanceError(DomainError):
    """A derived item is not faithfully grounded in its cited source.

    Raised when a :class:`~distil.domain.source_reference.SourceReference` does not resolve to the
    exact passage it claims. This is the enforcement point for Constitution Principle I
    (Source-Faithfulness): an item that fails this check must never be persisted as fact.
    """
