"""
Template and prompt management.

Prompts are loaded from:
1. User's .autonomous-agent/prompts/ directory (if exists)
2. Built-in package prompts
"""

from importlib import resources
from pathlib import Path

# User prompts directory
USER_PROMPTS_DIR = Path.home() / ".config" / "autonomous-agent" / "prompts"


def get_prompt(name: str) -> str:
    """Load a prompt template by name."""
    # Check user directory first
    user_prompt = USER_PROMPTS_DIR / f"{name}_prompt.md"
    if user_prompt.exists():
        return user_prompt.read_text()

    # Fall back to package prompts
    try:
        prompt_file = resources.files("autonomous_agent.prompts").joinpath(f"{name}_prompt.md")
        return prompt_file.read_text()
    except FileNotFoundError:
        raise ValueError(f"Prompt not found: {name}")


def get_template(template_type: str) -> str:
    """Get a specification template."""
    templates = {
        "app": _APP_SPEC_TEMPLATE,
        "feature": _FEATURE_SPEC_TEMPLATE,
    }

    if template_type not in templates:
        raise ValueError(f"Unknown template: {template_type}")

    return templates[template_type]


_APP_SPEC_TEMPLATE = '''<project_specification>
  <project_name>Your Project Name</project_name>

  <overview>
    Describe what you want to build in 2-3 paragraphs.
    Include the main purpose and key functionality.
  </overview>

  <technology_stack>
    <frontend>
      <framework>React with Vite (or your choice)</framework>
      <styling>Tailwind CSS</styling>
    </frontend>
    <backend>
      <runtime>Node.js with Express (or your choice)</runtime>
      <database>SQLite / PostgreSQL / etc.</database>
    </backend>
  </technology_stack>

  <core_features>
    <feature_1>
      - Feature description
      - User interaction details
      - Expected behavior
    </feature_1>

    <feature_2>
      - Feature description
      - User interaction details
    </feature_2>

    <!-- Add more features as needed -->
  </core_features>

  <success_criteria>
    <functionality>
      - List what must work
    </functionality>

    <user_experience>
      - UX requirements
    </user_experience>
  </success_criteria>
</project_specification>
'''

_FEATURE_SPEC_TEMPLATE = '''<feature_specification>
  <feature_name>Your Feature Name</feature_name>

  <overview>
    Describe the feature in 2-3 paragraphs.
    What does it do? Why is it needed?
  </overview>

  <existing_codebase_context>
    <project_structure>
      Describe your existing project structure:
      - Frontend: [e.g., React in /client, TypeScript]
      - Backend: [e.g., Express in /server, PostgreSQL]
      - Testing: [e.g., Jest, Playwright]
    </project_structure>

    <relevant_existing_code>
      Files the agent should study before implementing:
      - /path/to/similar/component.tsx - Similar component to reference
      - /path/to/api/client.ts - API client pattern to follow
    </relevant_existing_code>

    <patterns_to_follow>
      Coding patterns the agent MUST follow:
      - [e.g., All API calls use /src/api/client.ts]
      - [e.g., State management uses Zustand]
      - [e.g., Error handling pattern from ErrorBoundary.tsx]
    </patterns_to_follow>

    <do_not_modify>
      Areas the agent should NOT touch:
      - /path/to/auth/* - Authentication system
    </do_not_modify>
  </existing_codebase_context>

  <feature_requirements>
    <user_stories>
      - As a [user], I want to [action] so that [benefit]
    </user_stories>

    <acceptance_criteria>
      - Criterion 1
      - Criterion 2
    </acceptance_criteria>

    <technical_requirements>
      - Technical requirement 1
      - Technical requirement 2
    </technical_requirements>
  </feature_requirements>

  <testing_requirements>
    <existing_test_commands>
      - Unit: npm test
      - E2E: npm run test:e2e
      - Lint: npm run lint
    </existing_test_commands>
  </testing_requirements>

  <success_criteria>
    <definition_of_done>
      - All acceptance criteria met
      - All tests passing
      - Code follows existing patterns
      - No TypeScript errors
    </definition_of_done>
  </success_criteria>
</feature_specification>
'''
