# Contributing Guidelines

Thank you for your interest in contributing to the Computer Use Demo quickstart! This document outlines the process and guidelines for contributing to this project.

## Code of Conduct

Please be respectful and constructive in all interactions. We aim to maintain a welcoming and inclusive environment for all contributors.

## Contribution Policy

- Bugfixes and updates to our documentation that address correctness issues are always welcome
- Feature additions, refactors, and documentation updates beyond the scope of correctness (major changes) are accepted at the sole determination of the maintainers. We require each major change to be submitted in a separate Pull Request. We will assess new features under the following criteria:
  - Adherence to coding standards
  - Ease of use as a reference implementation
  - User experience
  - Applicability to a wide audience of developers
  - Minimization of third-party dependencies
  - Does not promote a product or service

Please open a github issue if you are need clarification on this policy or you want to discuss a new feature addition.

## Development Setup

1. Create and activate a Python virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Unix
   # or
   .venv\Scripts\activate  # On Windows
   ```

2. Install development dependencies:

   ```bash
   pip install -r dev-requirements.txt
   ```

3. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Development Process

1. Fork the repository and create a branch for your changes
2. Make your changes following our coding standards
3. Submit a pull request with a clear description of the changes

## Coding Standards

- Use clear, descriptive variable and function names
- Follow PEP 8 style guidelines for Python code
- Keep functions focused and single-purpose
- Avoid inline comments - code should be self-documenting
- Use type hints for all Python functions
- Use dataclasses for structured data (see `tools/base.py` for examples)
- All tools must inherit from `BaseAnthropicTool` and implement required methods
- Use abstract base classes (ABC) for defining interfaces
- Handle errors using `ToolError` and `ToolFailure` classes

## Code Quality Tools

We use several tools to maintain code quality:

- **Ruff**: For linting and formatting
  - Run `ruff check .` for linting
  - Run `ruff format .` for formatting
  - See `ruff.toml` for enabled rules
- **Pyright**: For type checking
  - Configuration in `pyproject.toml`
- **Pre-commit**: For automated checks before commits

## Testing

- Add tests for new functionality in the `tests/` directory
- Follow existing test patterns (see `tests/tools/` for examples)
- Use pytest fixtures where appropriate
- Run tests with:
  ```bash
  pytest
  ```
- Tests must pass in async mode (configured in pyproject.toml)

## Commit Guidelines

- All commits MUST be signed (use `git commit -S`)
- Write clear, descriptive commit messages
- Use present tense ("Add feature" not "Added feature")
- Reference issue numbers when applicable

## Pull Request Process

1. Update documentation as needed
2. Add tests for new functionality
3. Ensure all checks pass:
   - All tests pass
   - Ruff linting passes
   - Type checking passes
   - Pre-commit hooks pass
4. Request review from maintainers
5. Address review feedback

## Tool Development

When creating new tools:

1. Inherit from `BaseAnthropicTool`
2. Implement `__call__` and `to_params` methods
3. Use appropriate result types (`ToolResult`, `CLIResult`, or `ToolFailure`)
4. Add comprehensive tests
5. Document parameters and return types

## Documentation

- Keep README.md up to date
- Document new features and changes
- Use clear, concise language
- Include docstrings for all public classes and methods
- Use concise, single-line docstrings for simple functions
- For complex functions, include:
  - A brief description
  - Args/parameters if not obvious
  - Return value if not obvious
  - Any important notes about behavior

## Questions?

If you have questions, please open an issue for discussion.
