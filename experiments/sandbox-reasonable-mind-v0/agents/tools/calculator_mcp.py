#!/usr/bin/env python3

"""Simple calculator tool for basic math operations."""

import math

from mcp.server import FastMCP

mcp = FastMCP("Calculator")


@mcp.tool(name="calculator")
def calculator(number1: float, number2: float, operator: str) -> str:
    """Performs basic calculations with two numbers.

    Args:
        number1: First number in the calculation
        number2: Second number in the calculation
        operator: Operation symbol to perform (+, -, *, /, ^, sqrt)
               Note: Only these exact symbols are supported, not words

    Returns:
        Result of the calculation
    """
    try:
        if operator == "+":
            result = number1 + number2
        elif operator == "-":
            result = number1 - number2
        elif operator == "*":
            result = number1 * number2
        elif operator == "/":
            if number2 == 0:
                return "Error: Division by zero"
            result = number1 / number2
        elif operator == "^":
            result = number1**number2
        elif operator == "sqrt":
            if number1 < 0:
                return "Error: Cannot take square root of negative number"
            result = math.sqrt(number1)
        else:
            return f"Error: Unsupported operator '{operator}'"

        # Format the result
        if isinstance(result, float) and result.is_integer():
            result = int(result)

        return f"Result: {result}"
    except Exception as e:
        return f"Error: {str(e)}"


if __name__ == "__main__":
    mcp.run()
