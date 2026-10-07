"""
Unit tests — Entity Extractor (Fáze 49). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.entity_extractor import (
    Entity,
    EntityExtractor,
    EntityResult,
    EntityType,
)


def _types(result: EntityResult) -> set[str]:
    return {e.type for e in result.entities}


def _values(result: EntityResult, etype: str) -> list[str]:
    return [e.value for e in result.entities if e.type == etype]


# ── Individual entity types ──────────────────────────────────────────────────────

def test_extract_email():
    e = EntityExtractor()
    r = e.extract("Contact me at alice@example.com please.")
    assert "alice@example.com" in _values(r, "EMAIL")


def test_extract_url():
    e = EntityExtractor()
    r = e.extract("See https://example.com/docs for details.")
    assert any("example.com" in v for v in _values(r, "URL"))


def test_extract_date_iso():
    e = EntityExtractor()
    r = e.extract("The launch is on 2024-06-15 sharp.")
    assert "2024-06-15" in _values(r, "DATE")


def test_extract_date_month_name():
    e = EntityExtractor()
    r = e.extract("Due January 5, 2024 at noon.")
    assert any("January" in v for v in _values(r, "DATE"))


def test_extract_date_slash():
    e = EntityExtractor()
    r = e.extract("Filed 06/15/2024 today.")
    assert "06/15/2024" in _values(r, "DATE")


def test_extract_money_dollar():
    e = EntityExtractor()
    r = e.extract("It costs $1,200.50 total.")
    assert any("1,200" in v for v in _values(r, "MONEY"))


def test_extract_money_words():
    e = EntityExtractor()
    r = e.extract("Revenue was 5 million USD last year.")
    assert _values(r, "MONEY")


def test_extract_percent():
    e = EntityExtractor()
    r = e.extract("Growth of 25% year over year.")
    assert any("25" in v for v in _values(r, "PERCENT"))


def test_extract_phone():
    e = EntityExtractor()
    r = e.extract("Call 555-123-4567 now.")
    assert "555-123-4567" in _values(r, "PHONE")


def test_extract_proper_noun():
    e = EntityExtractor()
    r = e.extract("Barack Obama visited Berlin.")
    pns = _values(r, "PROPER_NOUN")
    assert "Barack Obama" in pns
    assert "Berlin" in pns


def test_extract_number():
    e = EntityExtractor()
    r = e.extract("There are 42 items in stock.")
    assert "42" in _values(r, "NUMBER")


# ── Priority / overlap ───────────────────────────────────────────────────────────

def test_percent_wins_over_number():
    e = EntityExtractor()
    r = e.extract("about 50%")
    # "50" should be claimed by PERCENT, not also emitted as NUMBER
    assert _values(r, "PERCENT")
    assert "50" not in _values(r, "NUMBER")


def test_money_wins_over_number():
    e = EntityExtractor()
    r = e.extract("price $100")
    assert _values(r, "MONEY")
    assert "100" not in _values(r, "NUMBER")


def test_date_wins_over_number():
    e = EntityExtractor()
    r = e.extract("on 2024-06-15")
    assert _values(r, "DATE")
    # date components not separately emitted as numbers
    assert "2024" not in _values(r, "NUMBER")


def test_email_not_split_into_proper_noun():
    e = EntityExtractor()
    r = e.extract("Email Alice at alice@example.com")
    assert "alice@example.com" in _values(r, "EMAIL")


# ── Entities sorted & offsets ────────────────────────────────────────────────────

def test_entities_sorted_by_start():
    e = EntityExtractor()
    r = e.extract("Call 555-123-4567 or email bob@test.com about 10%.")
    starts = [ent.start for ent in r.entities]
    assert starts == sorted(starts)


def test_offsets_slice_correctly():
    e = EntityExtractor()
    text = "Pay $50 now."
    r = e.extract(text)
    for ent in r.entities:
        assert text[ent.start:ent.end].strip() == ent.value


# ── Enabled types ────────────────────────────────────────────────────────────────

def test_enabled_types_filter():
    e = EntityExtractor(enabled_types=[EntityType.EMAIL])
    r = e.extract("alice@example.com paid $100 on 2024-01-01")
    assert _types(r) <= {"EMAIL"}


# ── Counts & empty ───────────────────────────────────────────────────────────────

def test_counts_by_type():
    e = EntityExtractor(enabled_types=[EntityType.EMAIL])
    r = e.extract("a@b.com and c@d.com")
    assert r.counts_by_type["EMAIL"] == 2


def test_empty_text():
    e = EntityExtractor()
    r = e.extract("")
    assert r.entity_count == 0
    assert r.entities == []


def test_no_entities():
    e = EntityExtractor(enabled_types=[EntityType.EMAIL])
    r = e.extract("just some lowercase words here")
    assert r.entity_count == 0


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    e = EntityExtractor()
    d = e.extract("Pay $50").to_dict()
    for key in ("entities", "counts_by_type", "entity_count"):
        assert key in d


def test_entity_to_dict_shape():
    ent = Entity("MONEY", "$50", 4, 7)
    assert ent.to_dict() == {"type": "MONEY", "value": "$50", "start": 4, "end": 7}


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    e = EntityExtractor(enabled_types=[EntityType.EMAIL, EntityType.PHONE])
    e.extract("a@b.com")
    e.extract("call 555-123-4567")
    m = e.metrics()
    assert m["total_extractions"] == 2
    assert m["total_entities"] == 2
    assert m["by_type"]["EMAIL"] == 1
    assert m["by_type"]["PHONE"] == 1


def test_metrics_reset():
    e = EntityExtractor()
    e.extract("alice@example.com")
    e.reset_metrics()
    m = e.metrics()
    assert m["total_extractions"] == 0
    assert m["by_type"] == {}


def test_metrics_shape():
    e = EntityExtractor()
    m = e.metrics()
    for key in ("total_extractions", "total_entities", "by_type",
                "avg_entities", "enabled_types"):
        assert key in m
