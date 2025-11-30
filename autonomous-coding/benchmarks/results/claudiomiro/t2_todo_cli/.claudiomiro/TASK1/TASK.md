@dependencies [TASK0]
# Task: Core CLI Implementation

## Summary
Implement the complete CLI application with all four commands (add, list, complete, delete) using Click framework, plus JSON storage functions for data persistence. This is the main implementation task that creates all business logic.

## Context Reference
**For complete environment context, see:**
- `../AI_PROMPT.md` - Contains full tech stack, CLI patterns, data structure, acceptance criteria, and constraints

**Task-Specific Context:**
- Files to create:
  - `src/todo_cli/cli.py` - Main CLI implementation with all commands
- Patterns to follow:
  - Click CLI pattern: AI_PROMPT.md:65-82
  - JSON storage pattern: AI_PROMPT.md:85-98
  - Todo data structure: AI_PROMPT.md:101-109
- Commands to implement:
  - `add <description>` - Add new todo with auto-increment ID
  - `list` - Display all todos with checkbox format
  - `complete <id>` - Mark todo as completed
  - `delete <id>` - Remove todo from storage

## Complexity
Medium

## Dependencies
Depends on: TASK0
Blocks: TASK2, TASKΩ
Parallel with: None

## Detailed Steps
1. Create `src/todo_cli/cli.py`
2. Implement storage functions: `load_todos()`, `save_todos()`
3. Implement Click group with `@click.group()`
4. Implement `add` command with description argument
5. Implement `list` command (handles empty list)
6. Implement `complete` command with ID argument
7. Implement `delete` command with ID argument
8. Handle all error cases with exit code 1

## Acceptance Criteria
### Core Commands
- [ ] `todo add "task description"` creates new todo with auto-incremented ID, stores in JSON
- [ ] `todo list` displays all todos with `[x]` for completed, `[ ]` for pending, numbered by ID
- [ ] `todo complete <id>` marks specified todo as completed
- [ ] `todo delete <id>` removes specified todo from storage
- [ ] `todo --help` shows usage information

### Data Persistence
- [ ] Todos stored in `todos.json` in working directory
- [ ] Each todo contains: `id` (int), `description` (str), `completed` (bool), `created_at` (ISO timestamp)
- [ ] IDs auto-increment (max existing ID + 1, or 1 if empty)
- [ ] Data persists between program runs

### Output Format
- [ ] List output: `1. [x] Completed task` or `2. [ ] Pending task`
- [ ] Success messages: "Added todo: ...", "Completed todo: ...", "Deleted todo: ..."
- [ ] Exit code 0 for success, 1 for errors

### Edge Cases
- [ ] Empty description on `add` → Error message, exit code 1
- [ ] Invalid/non-existent ID on `complete` → "Todo not found", exit code 1
- [ ] Invalid/non-existent ID on `delete` → "Todo not found", exit code 1
- [ ] Empty todo list on `list` → "No todos yet"

## Code Review Checklist
- [ ] Uses Click decorators: `@click.group()`, `@cli.command()`, `@click.argument()`
- [ ] Uses `click.echo()` for all output (not print)
- [ ] Uses `sys.exit(1)` or `raise SystemExit(1)` for errors
- [ ] Type hints on all functions
- [ ] No unnecessary classes (dict is sufficient)
- [ ] No extra features beyond spec (no due dates, priorities, etc.)
- [ ] ISO 8601 format for timestamps (`datetime.now().isoformat()`)

## Reasoning Trace
This task consolidates all CLI implementation because the commands are tightly coupled through shared storage functions. Splitting add/list/complete/delete into separate tasks would create unnecessary file conflicts and redundant setup. The Click pattern and JSON storage patterns are clearly provided in AI_PROMPT.md, so implementation should follow them exactly.
