"""Tests for Streamlit helper functions with edge case coverage."""

import asyncio
from unittest.mock import MagicMock, Mock, patch

import pytest
from browser_use_demo.loop import APIProvider
from browser_use_demo.streamlit import (
    authenticate,
    get_or_create_event_loop,
    setup_state,
)


class TestSetupState:
    """Test suite for setup_state function."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_fresh_initialization(self, mock_state, mock_environment):
        """Test setup_state with completely empty session state."""
        # Simulate empty session state
        mock_state.__contains__.return_value = False
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC

        with patch("browser_use_demo.tools.BrowserTool") as mock_browser:
            setup_state()

            # Check all defaults were set
            assert "messages" in mock_state.__setitem__.call_args_list[0][0]
            assert "api_key" in str(mock_state.__setitem__.call_args_list)
            assert "event_loop" in str(mock_state.__setitem__.call_args_list)

            # Browser tool should be created
            mock_browser.assert_called_once()

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_partial_initialization(self, mock_state):
        """Test setup_state when some keys already exist."""

        # Simulate partial state
        existing_keys = ["messages", "api_key"]

        def contains_side_effect(key):
            return key in existing_keys

        mock_state.__contains__.side_effect = contains_side_effect
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC

        with patch("browser_use_demo.tools.BrowserTool"):
            setup_state()

            # Only missing keys should be set
            set_keys = [call[0][0] for call in mock_state.__setitem__.call_args_list]
            assert "messages" not in set_keys
            assert "api_key" not in set_keys

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_missing_env_variables(self, mock_state, clean_environment):
        """Test setup_state when environment variables are missing."""

        mock_state.__contains__.return_value = False
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC

        with patch("browser_use_demo.tools.BrowserTool") as mock_browser:
            setup_state()

            # BrowserTool no longer takes dimensions as arguments
            mock_browser.assert_called_with()

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_lambda_evaluation(self, mock_state, mock_provider):
        """Test that lambda functions are evaluated correctly."""

        mock_state.__contains__.return_value = False
        mock_state.provider = mock_provider.ANTHROPIC

        setup_state()

        # Model should be set based on provider
        model_calls = [
            call
            for call in mock_state.__setitem__.call_args_list
            if call[0][0] == "model"
        ]
        assert len(model_calls) > 0

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_browser_tool_error(self, mock_state):
        """Test setup_state when BrowserTool initialization fails."""

        mock_state.__contains__.return_value = False
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC

        with patch("browser_use_demo.tools.BrowserTool") as mock_browser:
            mock_browser.side_effect = Exception("Browser init failed")

            # Should raise the exception
            with pytest.raises(Exception, match="Browser init failed"):
                setup_state()

    # Test removed - BrowserTool no longer reads dimensions from environment


class TestGetOrCreateEventLoop:
    """Test suite for get_or_create_event_loop function."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("asyncio.new_event_loop")
    @patch("asyncio.set_event_loop")
    def test_create_new_loop_when_none(self, mock_set_loop, mock_new_loop, mock_state):
        """Test creating new event loop when none exists."""

        mock_state.event_loop = None
        new_loop = Mock()
        mock_new_loop.return_value = new_loop

        result = get_or_create_event_loop()

        mock_new_loop.assert_called_once()
        mock_set_loop.assert_called_once_with(new_loop)
        assert mock_state.event_loop == new_loop
        assert result == new_loop

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("asyncio.new_event_loop")
    @patch("asyncio.set_event_loop")
    def test_create_new_loop_when_closed(
        self, mock_set_loop, mock_new_loop, mock_state
    ):
        """Test creating new event loop when existing is closed."""

        closed_loop = Mock()
        closed_loop.is_closed.return_value = True
        mock_state.event_loop = closed_loop

        new_loop = Mock()
        mock_new_loop.return_value = new_loop

        result = get_or_create_event_loop()

        mock_new_loop.assert_called_once()
        mock_set_loop.assert_called_once_with(new_loop)
        assert mock_state.event_loop == new_loop
        assert result == new_loop

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("asyncio.new_event_loop")
    @patch("asyncio.set_event_loop")
    def test_reuse_existing_open_loop(self, mock_set_loop, mock_new_loop, mock_state):
        """Test reusing existing open event loop."""

        existing_loop = Mock()
        existing_loop.is_closed.return_value = False
        mock_state.event_loop = existing_loop

        result = get_or_create_event_loop()

        mock_new_loop.assert_not_called()
        mock_set_loop.assert_called_once_with(existing_loop)
        assert result == existing_loop

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("asyncio.new_event_loop")
    def test_event_loop_creation_error(self, mock_new_loop, mock_state):
        """Test handling error during event loop creation."""

        mock_state.event_loop = None
        mock_new_loop.side_effect = RuntimeError("Cannot create loop")

        with pytest.raises(RuntimeError, match="Cannot create loop"):
            get_or_create_event_loop()

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("asyncio.set_event_loop")
    def test_set_event_loop_error(self, mock_set_loop, mock_state):
        """Test handling error when setting event loop."""

        mock_state.event_loop = None
        mock_set_loop.side_effect = RuntimeError("Cannot set loop")

        with pytest.raises(RuntimeError, match="Cannot set loop"):
            get_or_create_event_loop()


class TestAuthenticate:
    """Test suite for authenticate function."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.error")
    @patch("streamlit.stop")
    def test_authenticate_with_valid_key(
        self, mock_stop, mock_error, mock_state, mock_provider
    ):
        """Test authenticate with valid API key."""

        mock_state.provider = mock_provider.ANTHROPIC
        mock_state.api_key = "valid-key"

        result = authenticate()

        assert result is True
        mock_error.assert_not_called()
        mock_stop.assert_not_called()

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.error")
    @patch("streamlit.stop")
    def test_authenticate_with_missing_key(
        self, mock_stop, mock_error, mock_state, mock_provider
    ):
        """Test authenticate with missing API key."""

        mock_state.provider = mock_provider.ANTHROPIC
        mock_state.api_key = ""

        authenticate()

        mock_error.assert_called_once_with(
            "Please provide your Anthropic API key in the sidebar"
        )
        mock_stop.assert_called_once()
        # Function doesn't return after stop() in real scenario

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("streamlit.error")
    @patch("streamlit.stop")
    def test_authenticate_with_none_key(
        self, mock_stop, mock_error, mock_state, mock_provider
    ):
        """Test authenticate with None API key."""

        mock_state.provider = mock_provider.ANTHROPIC
        mock_state.api_key = None

        authenticate()

        mock_error.assert_called_once()
        mock_stop.assert_called_once()

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_authenticate_non_anthropic_provider(self, mock_state, mock_provider):
        """Test authenticate with non-Anthropic provider."""

        mock_state.provider = mock_provider.BEDROCK
        mock_state.api_key = ""  # Empty key should be OK for non-Anthropic

        result = authenticate()

        assert result is True


class TestEdgeCasesAndErrors:
    """Test edge cases and error conditions for helper functions."""

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_with_corrupted_state(self, mock_state):
        """Test setup_state with corrupted session state."""

        # Simulate corrupted state that raises on access
        mock_state.__contains__.side_effect = Exception("State corrupted")

        with pytest.raises(Exception, match="State corrupted"):
            setup_state()

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_concurrent_setup_state_calls(self, mock_state):
        """Test concurrent calls to setup_state."""
        import threading

        mock_state.__contains__.return_value = False
        # Set provider to valid enum value so lambda can access it
        mock_state.provider = APIProvider.ANTHROPIC
        errors = []

        def run_setup():
            try:
                with patch("browser_use_demo.tools.BrowserTool"):
                    setup_state()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=run_setup) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should handle concurrent access without crashes
        assert len(errors) == 0

    @patch("streamlit.session_state", new_callable=MagicMock)
    @patch("asyncio.get_event_loop")
    def test_get_or_create_with_running_loop(self, mock_get_loop, mock_state):
        """Test get_or_create_event_loop when another loop is running."""

        mock_state.event_loop = None
        running_loop = Mock(spec=asyncio.AbstractEventLoop)
        running_loop.is_running.return_value = True
        mock_get_loop.return_value = running_loop

        # Should create new loop despite running loop exists
        with patch("asyncio.new_event_loop") as mock_new:
            new_loop = Mock(spec=asyncio.AbstractEventLoop)
            new_loop.is_closed.return_value = False
            mock_new.return_value = new_loop

            with patch("asyncio.set_event_loop"):
                result = get_or_create_event_loop()
                assert result == new_loop

    @patch("streamlit.session_state", new_callable=MagicMock)
    def test_setup_state_with_readonly_state(self, mock_state):
        """Test setup_state when session state is read-only."""

        mock_state.__contains__.return_value = False
        mock_state.__setitem__.side_effect = AttributeError("Read-only state")

        with pytest.raises(AttributeError, match="Read-only state"):
            setup_state()

    # Test removed - BrowserTool no longer reads dimensions from environment
