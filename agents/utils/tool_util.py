"""Tool execution utility with parallel execution support."""

import asyncio
from typing import Any


async def _execute_single_tool(
    call: Any, tool_dict: dict[str, Any]
) -> dict[str, Any]:
    """Execute a single tool and handle errors."""
    response = {"type": "tool_result", "tool_use_id": call.id}

    try:
        # Execute the tool directly
        result = await tool_dict[call.name].execute(**call.input)
        response["content"] = str(result)
    except KeyError:
        response["content"] = f"Tool '{call.name}' not found"
        response["is_error"] = True
    except Exception as e:
        response["content"] = f"Error executing tool: {str(e)}"
        response["is_error"] = True

    return response


async def execute_tools(
    tool_calls: list[Any], tool_dict: dict[str, Any], parallel: bool = True
) -> list[dict[str, Any]]:
    """Execute multiple tools sequentially or in parallel."""

    if parallel:
        return await asyncio.gather(
            *[_execute_single_tool(call, tool_dict) for call in tool_calls]
        )
    else:
        return [
            await _execute_single_tool(call, tool_dict) for call in tool_calls
        ]
