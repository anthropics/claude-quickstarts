"""Unit testy — UserRateLimiter per-user RPM (Fáze 5)."""
import pytest

from core.user_limiter import UserRateLimiter


@pytest.mark.unit
def test_no_limit_allows_all_requests():
    ul = UserRateLimiter()
    for _ in range(1000):
        assert ul.check_and_record("alice") is True


@pytest.mark.unit
def test_set_limit_blocks_excess_requests():
    ul = UserRateLimiter()
    ul.set_limit("bob", 3)
    assert ul.check_and_record("bob") is True
    assert ul.check_and_record("bob") is True
    assert ul.check_and_record("bob") is True
    assert ul.check_and_record("bob") is False  # 4. požadavek zamítnut


@pytest.mark.unit
def test_reset_clears_counter_and_limit():
    ul = UserRateLimiter()
    ul.set_limit("carol", 2)
    ul.check_and_record("carol")
    ul.check_and_record("carol")
    ul.reset("carol")
    status = ul.get_status("carol")
    assert status["rpm_limit"] is None
    assert status["requests_last_minute"] == 0
    assert ul.check_and_record("carol") is True


@pytest.mark.unit
def test_get_status_reflects_current_count():
    ul = UserRateLimiter()
    ul.set_limit("dave", 10)
    ul.check_and_record("dave")
    ul.check_and_record("dave")
    status = ul.get_status("dave")
    assert status["rpm_limit"] == 10
    assert status["requests_last_minute"] == 2
    assert status["limited"] is False


@pytest.mark.unit
def test_set_limit_zero_removes_limit():
    ul = UserRateLimiter()
    ul.set_limit("eve", 5)
    ul.set_limit("eve", 0)
    status = ul.get_status("eve")
    assert status["rpm_limit"] is None
    for _ in range(10):
        assert ul.check_and_record("eve") is True
