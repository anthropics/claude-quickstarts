"""
Unit tests — PII Anonymizer (Fáze 39). Fully offline, deterministic.
"""

from __future__ import annotations

import pytest

from core.anonymizer import (
    AnonymizationResult,
    PIIAnonymizer,
    PIIType,
)


# ── Detection ────────────────────────────────────────────────────────────────────

def test_detect_email():
    a = PIIAnonymizer()
    found = a.detect("reach me at john@example.com today")
    assert any(f["type"] == "EMAIL" and f["value"] == "john@example.com" for f in found)


def test_detect_multiple_types():
    a = PIIAnonymizer()
    found = a.detect("email a@b.com phone 555-123-4567 ssn 123-45-6789")
    types = {f["type"] for f in found}
    assert "EMAIL" in types
    assert "PHONE" in types
    assert "SSN" in types


def test_detect_none():
    a = PIIAnonymizer()
    assert a.detect("no personal data here") == []


def test_detect_positions_sorted():
    a = PIIAnonymizer()
    found = a.detect("first a@b.com then c@d.com")
    starts = [f["start"] for f in found]
    assert starts == sorted(starts)


# ── Anonymize basics ─────────────────────────────────────────────────────────────

def test_anonymize_email_placeholder():
    a = PIIAnonymizer()
    result = a.anonymize("contact john@example.com please")
    assert "[EMAIL_1]" in result.anonymized_text
    assert "john@example.com" not in result.anonymized_text
    assert result.mapping["[EMAIL_1]"] == "john@example.com"


def test_anonymize_ssn():
    a = PIIAnonymizer()
    result = a.anonymize("SSN: 123-45-6789")
    assert "[SSN_1]" in result.anonymized_text


def test_anonymize_credit_card():
    a = PIIAnonymizer()
    result = a.anonymize("card 4111 1111 1111 1111 ok")
    assert "[CREDIT_CARD_1]" in result.anonymized_text


def test_anonymize_ip():
    a = PIIAnonymizer()
    result = a.anonymize("server at 192.168.1.1 listening")
    assert "[IP_1]" in result.anonymized_text


def test_anonymize_url():
    a = PIIAnonymizer()
    result = a.anonymize("see https://example.com/page now")
    assert "[URL_1]" in result.anonymized_text


def test_anonymize_no_pii_unchanged():
    a = PIIAnonymizer()
    result = a.anonymize("plain text only")
    assert result.anonymized_text == "plain text only"
    assert result.mapping == {}


# ── Stable placeholders (dedup) ──────────────────────────────────────────────────

def test_repeated_value_shares_placeholder():
    a = PIIAnonymizer()
    result = a.anonymize("mail x@y.com and again x@y.com")
    # one mapping entry, placeholder used twice
    assert len(result.mapping) == 1
    assert result.anonymized_text.count("[EMAIL_1]") == 2


def test_distinct_values_distinct_placeholders():
    a = PIIAnonymizer()
    result = a.anonymize("a@b.com and c@d.com")
    assert "[EMAIL_1]" in result.anonymized_text
    assert "[EMAIL_2]" in result.anonymized_text
    assert len(result.mapping) == 2


# ── Restore round-trip ───────────────────────────────────────────────────────────

def test_restore_round_trip():
    a = PIIAnonymizer()
    original = "email a@b.com phone 555-123-4567"
    result = a.anonymize(original)
    restored = PIIAnonymizer.restore(result.anonymized_text, result.mapping)
    assert restored == original


def test_restore_handles_double_digit_indices():
    a = PIIAnonymizer()
    # 11 distinct emails → placeholders EMAIL_1 .. EMAIL_11
    emails = " ".join(f"user{i}@x.com" for i in range(11))
    result = a.anonymize(emails)
    restored = PIIAnonymizer.restore(result.anonymized_text, result.mapping)
    assert restored == emails
    # ensure EMAIL_1 didn't corrupt EMAIL_11
    assert "user10@x.com" in restored


def test_restore_empty_mapping():
    assert PIIAnonymizer.restore("no tokens", {}) == "no tokens"


# ── Enabled types filter ─────────────────────────────────────────────────────────

def test_enabled_types_restricts():
    a = PIIAnonymizer(enabled_types=[PIIType.EMAIL])
    result = a.anonymize("a@b.com and 555-123-4567")
    assert "[EMAIL_1]" in result.anonymized_text
    # phone left intact
    assert "555-123-4567" in result.anonymized_text


def test_detect_respects_enabled_types():
    a = PIIAnonymizer(enabled_types=[PIIType.SSN])
    found = a.detect("a@b.com 123-45-6789")
    assert {f["type"] for f in found} == {"SSN"}


# ── Overlap handling ─────────────────────────────────────────────────────────────

def test_email_wins_over_url_like_overlap():
    a = PIIAnonymizer()
    # email pattern listed first; ensure no double-claim
    result = a.anonymize("contact a@b.com")
    assert result.entity_count == 1


# ── Result shape ─────────────────────────────────────────────────────────────────

def test_result_to_dict_shape():
    a = PIIAnonymizer()
    result = a.anonymize("a@b.com")
    d = result.to_dict()
    for key in ("anonymized_text", "mapping", "entity_counts", "entity_count"):
        assert key in d


def test_entity_counts_by_type():
    a = PIIAnonymizer()
    result = a.anonymize("a@b.com c@d.com 192.168.0.1")
    assert result.entity_counts["EMAIL"] == 2
    assert result.entity_counts["IP"] == 1


# ── Metrics ──────────────────────────────────────────────────────────────────────

def test_metrics_accumulate():
    a = PIIAnonymizer()
    a.anonymize("a@b.com")
    a.anonymize("phone 555-123-4567")
    m = a.metrics()
    assert m["total_anonymized"] == 2
    assert m["total_entities"] == 2
    assert m["by_type"]["EMAIL"] == 1
    assert m["by_type"]["PHONE"] == 1


def test_metrics_avg():
    a = PIIAnonymizer()
    a.anonymize("a@b.com c@d.com")  # 2 entities
    m = a.metrics()
    assert m["avg_entities_per_call"] == 2.0


def test_metrics_reset():
    a = PIIAnonymizer()
    a.anonymize("a@b.com")
    a.reset_metrics()
    m = a.metrics()
    assert m["total_anonymized"] == 0
    assert m["by_type"] == {}


def test_metrics_shape():
    a = PIIAnonymizer()
    m = a.metrics()
    for key in ("total_anonymized", "total_entities", "by_type",
                "avg_entities_per_call", "enabled_types"):
        assert key in m


def test_metrics_enabled_types_listed():
    a = PIIAnonymizer(enabled_types=[PIIType.EMAIL, PIIType.PHONE])
    m = a.metrics()
    assert set(m["enabled_types"]) == {"EMAIL", "PHONE"}
