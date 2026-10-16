"""(De)serialization between domain value objects and JSON stored in SQLite text columns.

Kept tiny and explicit so the stored shape is obvious and portable to a future Postgres schema.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from distil.domain.material import PageSpan
from distil.domain.source_reference import SourceReference


def sources_to_json(sources: Sequence[SourceReference]) -> str:
    return json.dumps(
        [
            {
                "material_id": s.material_id,
                "start_offset": s.start_offset,
                "end_offset": s.end_offset,
                "quote": s.quote,
                "page": s.page,
            }
            for s in sources
        ]
    )


def sources_from_json(raw: str) -> tuple[SourceReference, ...]:
    return tuple(
        SourceReference(
            material_id=d["material_id"],
            start_offset=d["start_offset"],
            end_offset=d["end_offset"],
            quote=d["quote"],
            page=d.get("page"),
        )
        for d in json.loads(raw)
    )


def page_map_to_json(page_map: Sequence[PageSpan]) -> str:
    return json.dumps(
        [
            {"start_offset": p.start_offset, "end_offset": p.end_offset, "page": p.page}
            for p in page_map
        ]
    )


def page_map_from_json(raw: str) -> tuple[PageSpan, ...]:
    return tuple(
        PageSpan(start_offset=d["start_offset"], end_offset=d["end_offset"], page=d["page"])
        for d in json.loads(raw)
    )
