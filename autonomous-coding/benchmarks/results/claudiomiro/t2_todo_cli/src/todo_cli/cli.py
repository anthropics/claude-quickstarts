"""Todo CLI - Command-line interface for managing todo items."""
import json
import sys
from datetime import datetime
from pathlib import Path

import click

DATA_FILE = Path("todos.json")


def load_todos() -> list[dict]:
    """Load todos from JSON file."""
    if not DATA_FILE.exists():
        return []
    content = DATA_FILE.read_text()
    if not content.strip():
        return []
    return json.loads(content)


def save_todos(todos: list[dict]) -> None:
    """Save todos to JSON file."""
    DATA_FILE.write_text(json.dumps(todos, indent=2))


@click.group()
def cli() -> None:
    """Todo CLI - Manage your tasks from the command line."""
    pass


@cli.command()
@click.argument('description')
def add(description: str) -> None:
    """Add a new todo item."""
    if not description.strip():
        click.echo("Error: Description cannot be empty")
        sys.exit(1)

    todos = load_todos()
    new_id = max((t['id'] for t in todos), default=0) + 1
    new_todo = {
        "id": new_id,
        "description": description,
        "completed": False,
        "created_at": datetime.now().isoformat()
    }
    todos.append(new_todo)
    save_todos(todos)
    click.echo(f"Added todo: {description}")


@cli.command('list')
def list_todos() -> None:
    """List all todo items."""
    todos = load_todos()
    if not todos:
        click.echo("No todos yet")
        return

    for todo in todos:
        checkbox = "[x]" if todo['completed'] else "[ ]"
        click.echo(f"{todo['id']}. {checkbox} {todo['description']}")


@cli.command()
@click.argument('id', type=int)
def complete(id: int) -> None:
    """Mark a todo as completed."""
    todos = load_todos()
    for todo in todos:
        if todo['id'] == id:
            todo['completed'] = True
            save_todos(todos)
            click.echo(f"Completed todo: {todo['description']}")
            return

    click.echo("Todo not found")
    sys.exit(1)


@cli.command()
@click.argument('id', type=int)
def delete(id: int) -> None:
    """Delete a todo item."""
    todos = load_todos()
    for i, todo in enumerate(todos):
        if todo['id'] == id:
            description = todo['description']
            todos.pop(i)
            save_todos(todos)
            click.echo(f"Deleted todo: {description}")
            return

    click.echo("Todo not found")
    sys.exit(1)


if __name__ == '__main__':
    cli()
