# Browser Use Demo - Test Suite

Comprehensive test suite for the refactored Browser Use Demo with extensive edge case coverage.

## Installation

```bash
# Install test dependencies
pip install -r test-requirements.txt

# Or install with extras
pip install -e ".[test]"
```

## Running Tests

### Run all tests
```bash
pytest tests/
```

### Run with coverage report
```bash
pytest tests/ --cov=browser_tools_api_demo --cov-report=html
# Open htmlcov/index.html to view coverage report
```

### Run specific test file
```bash
pytest tests/test_message_renderer.py -v
```

### Run specific test class or method
```bash
pytest tests/test_message_renderer.py::TestMessageRenderer -v
pytest tests/test_message_renderer.py::TestRenderMethod::test_render_string_message -v
```

### Run tests by marker
```bash
# Run only integration tests
pytest -m integration

# Run tests excluding integration
pytest -m "not integration"

# Run async tests
pytest -m asyncio
```

## Test Structure

```
tests/
├── conftest.py                      # Shared fixtures and mocks
├── test_message_renderer.py         # MessageRenderer class tests (~300 test cases)
├── test_streamlit_helpers.py        # Helper function tests (~150 test cases)
└── test_integration.py              # End-to-end integration tests (~50 test cases)
```

## Test Coverage

The test suite covers:

### MessageRenderer (`test_message_renderer.py`)
- Initialization with various state configurations
- Rendering all message types (string, dict, ToolResult)
- Conversation history rendering with complex structures
- Edge cases: empty messages, None values, circular references
- Error handling: malformed data, missing fields, exceptions
- Unicode and special character handling
- Performance with large messages

### Streamlit Helpers (`test_streamlit_helpers.py`)
- `setup_state()` with fresh and partial initialization
- Environment variable handling (present/missing/invalid)
- Lambda evaluation in state initialization
- `get_or_create_event_loop()` with various loop states
- `authenticate()` with different providers and key states
- Concurrent access and thread safety
- Error recovery scenarios

### Integration Tests (`test_integration.py`)
- Complete message rendering pipeline
- State initialization and persistence
- Event loop management with async operations
- Error propagation across components
- Full user interaction workflow
- Performance with large datasets (1000+ messages)
- Deeply nested content structures

## Edge Cases Covered

1. **Boundary Conditions**
   - Empty strings, lists, dictionaries
   - Single item collections
   - Maximum size inputs (100k+ character messages)
   - Null/None values

2. **Type Mismatches**
   - Wrong types for expected fields
   - Missing required fields
   - Extra unexpected fields
   - Invalid message structures

3. **State Inconsistencies**
   - Tools referenced but not in session_state
   - Partially initialized state
   - Concurrent modifications
   - Corrupted state

4. **Error Conditions**
   - Import errors
   - Asyncio exceptions
   - Environment variable errors
   - Lambda evaluation failures
   - Base64 decode errors

5. **Performance Edge Cases**
   - Very large message histories (1000+ messages)
   - Deeply nested content (100+ levels)
   - Circular references
   - Unicode and special characters

## Mocking Strategy

### Streamlit Components
All Streamlit components are mocked to enable testing without a running Streamlit server:
- `st.session_state`
- `st.chat_message`
- `st.markdown`, `st.write`, `st.error`, `st.code`, `st.image`
- `st.chat_input`, `st.stop`

### External Dependencies
- `BrowserTool` - Mocked to avoid Playwright dependencies
- `asyncio` event loops - Mocked for controlled testing
- Environment variables - Mocked via `monkeypatch`

## Fixtures

Key fixtures provided in `conftest.py`:

- `mock_streamlit` - Complete Streamlit mocking setup
- `mock_browser_tool` - BrowserTool mock
- `sample_tool_result` - Various ToolResult configurations
- `sample_messages` - Diverse message structures for testing
- `edge_case_messages` - Messages designed to trigger edge cases
- `mock_asyncio_loop` - Controlled event loop for testing
- `mock_environment` - Environment variable setup
- `clean_environment` - Remove environment variables

## Continuous Integration

To run tests in CI:

```bash
# Install dependencies
pip install -e ".[test]"

# Run tests with coverage
pytest tests/ --cov=browser_tools_api_demo --cov-report=xml --cov-report=term

# Generate coverage badge
coverage-badge -o coverage.svg
```

## Contributing

When adding new features or refactoring:
1. Add corresponding tests for new functionality
2. Ensure all edge cases are covered
3. Run the full test suite before committing
4. Maintain >95% code coverage
5. Update this README if test structure changes