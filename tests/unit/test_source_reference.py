"""Unit tests for SourceReference — the source-faithfulness backbone (Principle I)."""

from __future__ import annotations

import pytest

from distil.domain.errors import ProvenanceError
from distil.domain.source_reference import SourceReference

CONTENT = "Backpropagation computes gradients via the chain rule."
#          0123456789...                      ^            ^


def test_faithful_reference_matches_slice() -> None:
    ref = SourceReference(material_id="m1", start_offset=0, end_offset=15, quote="Backpropagation")
    assert ref.is_faithful_to(CONTENT)
    ref.validate_against(CONTENT)  # does not raise


def test_quote_mismatch_is_unfaithful() -> None:
    ref = SourceReference(material_id="m1", start_offset=0, end_offset=15, quote="Gradient descent")
    assert not ref.is_faithful_to(CONTENT)
    with pytest.raises(ProvenanceError):
        ref.validate_against(CONTENT)


def test_span_beyond_content_is_unfaithful() -> None:
    ref = SourceReference(material_id="m1", start_offset=0, end_offset=9999, quote="x")
    assert not ref.is_faithful_to(CONTENT)
    with pytest.raises(ProvenanceError):
        ref.validate_against(CONTENT)


@pytest.mark.parametrize(
    ("start", "end"),
    [(-1, 5), (5, 5), (10, 3)],
)
def test_invalid_offsets_rejected_at_construction(start: int, end: int) -> None:
    with pytest.raises(ProvenanceError):
        SourceReference(material_id="m1", start_offset=start, end_offset=end, quote="x")


def test_page_must_be_positive_when_present() -> None:
    with pytest.raises(ProvenanceError):
        SourceReference(material_id="m1", start_offset=0, end_offset=3, quote="Bac", page=0)
