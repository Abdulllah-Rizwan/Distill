"""Provenance enforcement — the gate that keeps ungrounded items out of the graph (Principle I).

Every source reference on a derived item must resolve to the exact passage it claims in the cited
material. References that fail are dropped; an item left with no faithful source is discarded by the
caller. This is applied during graph building, before anything is persisted.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from distil.domain.material import Material
from distil.domain.source_reference import SourceReference


def is_faithful(ref: SourceReference, materials_by_id: Mapping[str, Material]) -> bool:
    """True iff ``ref`` points at a known material and quotes it exactly."""
    material = materials_by_id.get(ref.material_id)
    return material is not None and ref.is_faithful_to(material.content_text)


def keep_faithful(
    refs: Sequence[SourceReference], materials_by_id: Mapping[str, Material]
) -> tuple[SourceReference, ...]:
    """Return only the references that are faithful to their cited material."""
    return tuple(r for r in refs if is_faithful(r, materials_by_id))
