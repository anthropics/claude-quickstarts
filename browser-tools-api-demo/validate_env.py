#!/usr/bin/env python3
"""Validate environment configuration before startup."""

import os
import sys
from pathlib import Path


def validate_env():
    """Validate required environment variables are set."""
    errors = []

    # Check if running with docker-compose (preferred)
    if not os.environ.get('ANTHROPIC_API_KEY'):
        print("\n" + "="*60)
        print("ERROR: Missing required configuration!")
        print("="*60)
        print("\nThe Browser Tools API Demo requires proper configuration to run.")
        print("\n🔧 RECOMMENDED: Use docker-compose with a .env file:")
        print("  1. Copy the example environment file:")
        print("     cp .env.example .env")
        print("  2. Edit .env and add your Anthropic API key")
        print("  3. Run with docker-compose:")
        print("     docker-compose up --build")
        print("="*60)
        sys.exit(1)

    # Required variables with defaults for docker build compatibility
    required_vars = {
        'ANTHROPIC_API_KEY': 'Anthropic API key for Claude',
    }

    # These should be set but have build-time defaults
    recommended_vars = {
        'DISPLAY_WIDTH': 'Display width in pixels (e.g., 1920)',
        'DISPLAY_HEIGHT': 'Display height in pixels (e.g., 1080)',
        'BROWSER_WIDTH': 'Browser viewport width in pixels',
        'BROWSER_HEIGHT': 'Browser viewport height in pixels',
    }

    # Check API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key or api_key == 'your_anthropic_api_key_here' or len(api_key) < 10:
        errors.append("  ANTHROPIC_API_KEY: Must be a valid API key")

    # Check recommended variables (warn if not set)
    warnings = []
    for var, description in recommended_vars.items():
        value = os.environ.get(var)
        if not value:
            # Use defaults from Dockerfile build
            if var == 'DISPLAY_WIDTH' or var == 'BROWSER_WIDTH':
                os.environ[var] = os.environ.get('WIDTH', '1920')
            elif var == 'DISPLAY_HEIGHT' or var == 'BROWSER_HEIGHT':
                os.environ[var] = os.environ.get('HEIGHT', '1080')
            warnings.append(f"  {var}: Using default value {os.environ.get(var, 'unknown')}")
        elif var in ['DISPLAY_WIDTH', 'DISPLAY_HEIGHT', 'BROWSER_WIDTH', 'BROWSER_HEIGHT']:
            try:
                int_val = int(value)
                if int_val < 100 or int_val > 10000:
                    errors.append(f"  {var}: Must be between 100 and 10000 (got {value})")
            except ValueError:
                errors.append(f"  {var}: Must be a valid integer (got '{value}')")

    # Optional but recommended to be consistent
    if os.environ.get('DISPLAY_WIDTH') != os.environ.get('BROWSER_WIDTH'):
        print("WARNING: DISPLAY_WIDTH and BROWSER_WIDTH are different.")
        print(f"  DISPLAY_WIDTH={os.environ.get('DISPLAY_WIDTH')}")
        print(f"  BROWSER_WIDTH={os.environ.get('BROWSER_WIDTH')}")
        print("  This may cause viewport issues.")

    if os.environ.get('DISPLAY_HEIGHT') != os.environ.get('BROWSER_HEIGHT'):
        print("WARNING: DISPLAY_HEIGHT and BROWSER_HEIGHT are different.")
        print(f"  DISPLAY_HEIGHT={os.environ.get('DISPLAY_HEIGHT')}")
        print(f"  BROWSER_HEIGHT={os.environ.get('BROWSER_HEIGHT')}")
        print("  This may cause viewport issues.")

    if warnings:
        print("\nℹ️  Using default values for:")
        for warning in warnings:
            print(warning)

    if errors:
        print("\n" + "="*60)
        print("ERROR: Configuration issues detected:")
        print("="*60)
        for error in errors:
            print(error)
        print("\nTo fix this, please use docker-compose with a .env file:")
        print("  cp .env.example .env")
        print("  # Edit .env with your API key")
        print("  docker-compose up --build")
        print("="*60)
        sys.exit(1)

    print("\n✓ Environment validation passed")
    print(f"  Display: {os.environ.get('DISPLAY_WIDTH', os.environ.get('WIDTH', '1920'))}x{os.environ.get('DISPLAY_HEIGHT', os.environ.get('HEIGHT', '1080'))}")
    print(f"  Browser: {os.environ.get('BROWSER_WIDTH', os.environ.get('WIDTH', '1920'))}x{os.environ.get('BROWSER_HEIGHT', os.environ.get('HEIGHT', '1080'))}")


if __name__ == "__main__":
    validate_env()
