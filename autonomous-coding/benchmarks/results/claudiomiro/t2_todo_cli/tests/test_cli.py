"""Tests for the Todo CLI application."""
from click.testing import CliRunner
from todo_cli.cli import cli

# Happy Path Tests (4)

def test_add_todo():
    """Add a todo successfully, verify confirmation output."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['add', 'Buy groceries'])
        assert result.exit_code == 0
        assert 'Added' in result.output


def test_list_todos():
    """List todos shows correct format with checkbox."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ['add', 'Buy groceries'])
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        assert 'Buy groceries' in result.output
        assert '[ ]' in result.output


def test_complete_todo():
    """Mark todo complete, verify status change."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ['add', 'Buy groceries'])
        result = runner.invoke(cli, ['complete', '1'])
        assert result.exit_code == 0
        assert 'Completed' in result.output


def test_delete_todo():
    """Delete todo, verify removal."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ['add', 'Buy groceries'])
        result = runner.invoke(cli, ['delete', '1'])
        assert result.exit_code == 0
        assert 'Deleted' in result.output


# Edge Case Tests (4)

def test_add_empty_description():
    """Empty description shows error, exit code 1."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['add', ''])
        assert result.exit_code == 1
        assert 'empty' in result.output.lower()


def test_complete_invalid_id():
    """Invalid ID shows 'Todo not found', exit code 1."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['complete', '999'])
        assert result.exit_code == 1
        assert 'not found' in result.output.lower()


def test_delete_invalid_id():
    """Invalid ID shows 'Todo not found', exit code 1."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['delete', '999'])
        assert result.exit_code == 1
        assert 'not found' in result.output.lower()


def test_list_empty():
    """Empty list shows 'No todos yet'."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        assert 'No todos yet' in result.output


# Integration Tests (2)

def test_persistence():
    """Data persists across CLI invocations."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ['add', 'Task 1'])
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        assert 'Task 1' in result.output


def test_complete_workflow():
    """Add → Complete → List shows [x]."""
    runner = CliRunner()
    with runner.isolated_filesystem():
        runner.invoke(cli, ['add', 'Task 1'])
        runner.invoke(cli, ['complete', '1'])
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        assert '[x]' in result.output
