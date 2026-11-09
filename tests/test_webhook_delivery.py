"""Tests for webhook retry and dead-letter queue logic."""

import pytest

from src.services.events import MAX_ATTEMPTS, RETRY_DELAYS, _handle_failure


@pytest.fixture
def mock_delivery():
    """Create a mock delivery-like object for testing _handle_failure."""

    class MockDelivery:
        def __init__(self):
            self.id = "test-delivery-id"
            self.event_id = "test-event-id"
            self.attempts = 1
            self.max_attempts = MAX_ATTEMPTS
            self.status = "pending"
            self.error_message = None
            self.next_retry_at = None

    return MockDelivery()


class TestHandleFailure:
    def test_schedules_retry_on_first_failure(self, mock_delivery):
        mock_delivery.attempts = 1
        _handle_failure(mock_delivery, "Connection refused")
        assert mock_delivery.status == "pending"
        assert mock_delivery.next_retry_at is not None
        assert mock_delivery.error_message == "Connection refused"

    def test_moves_to_dead_letter_on_max_attempts(self, mock_delivery):
        mock_delivery.attempts = MAX_ATTEMPTS
        _handle_failure(mock_delivery, "Still failing")
        assert mock_delivery.status == "failed"
        assert mock_delivery.error_message == "Still failing"

    def test_retry_delays_escalate(self, mock_delivery):
        """Each retry should have a longer delay than the previous."""
        delays = []
        for attempt in range(1, MAX_ATTEMPTS):
            mock_delivery.attempts = attempt
            mock_delivery.next_retry_at = None
            _handle_failure(mock_delivery, "error")
            if mock_delivery.next_retry_at:
                delays.append(mock_delivery.next_retry_at)

        # Verify delays are increasing
        for i in range(1, len(delays)):
            assert delays[i] > delays[i - 1]


class TestRetryConstants:
    def test_max_attempts_matches_delays(self):
        assert MAX_ATTEMPTS == len(RETRY_DELAYS) + 1

    def test_delays_are_increasing(self):
        for i in range(1, len(RETRY_DELAYS)):
            assert RETRY_DELAYS[i] > RETRY_DELAYS[i - 1]
