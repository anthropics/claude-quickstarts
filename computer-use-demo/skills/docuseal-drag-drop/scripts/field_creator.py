#!/usr/bin/env python3
"""
DocuSeal Field Creator

Creates or updates fields in DocuSeal templates via REST API.
Provides reliable, deterministic field creation without browser automation.

Usage:
    python field_creator.py --template-id "abc123" --field-json '{"name":"Signature",...}'
    python field_creator.py --template-id "abc123" --fields-file fields.json
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, List, Any, Optional


class DocuSealAPIClient:
    """Client for interacting with DocuSeal REST API."""

    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize DocuSeal API client.

        Args:
            base_url: DocuSeal instance URL (defaults to DOCUSEAL_URL env var)
            api_key: API key for authentication (defaults to DOCUSEAL_API_KEY env var)
        """
        self.base_url = (base_url or os.getenv("DOCUSEAL_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("DOCUSEAL_API_KEY", "")

        if not self.base_url:
            raise ValueError("DocuSeal URL not configured. Set DOCUSEAL_URL environment variable.")
        if not self.api_key:
            raise ValueError("DocuSeal API key not configured. Set DOCUSEAL_API_KEY environment variable.")

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        return {
            "X-Auth-Token": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def create_fields(self, template_id: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create or update fields in a template.

        Args:
            template_id: Template ID to update
            fields: List of field configurations

        Returns:
            API response as dictionary

        Raises:
            requests.HTTPError: If API request fails
        """
        url = f"{self.base_url}/api/templates/{template_id}"

        payload = {"fields": fields}

        try:
            response = requests.put(
                url,
                headers=self._get_headers(),
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ API request failed: {e}", file=sys.stderr)
            if hasattr(e, 'response') and e.response is not None:
                print(f"   Status: {e.response.status_code}", file=sys.stderr)
                print(f"   Response: {e.response.text}", file=sys.stderr)
            raise

    def get_template(self, template_id: str) -> Dict[str, Any]:
        """
        Get template details.

        Args:
            template_id: Template ID to retrieve

        Returns:
            Template data as dictionary
        """
        url = f"{self.base_url}/api/templates/{template_id}"

        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                timeout=30
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to get template: {e}", file=sys.stderr)
            raise


def validate_field_config(field: Dict[str, Any]) -> List[str]:
    """
    Validate field configuration structure.

    Args:
        field: Field configuration dictionary

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    # Required fields
    if "name" not in field:
        errors.append("Field missing required 'name' property")
    if "type" not in field:
        errors.append("Field missing required 'type' property")
    if "areas" not in field:
        errors.append("Field missing required 'areas' property")

    # Validate type
    valid_types = [
        "signature", "initials", "text", "date", "number",
        "checkbox", "radio", "select", "multi-select",
        "image", "file", "payment"
    ]
    if "type" in field and field["type"] not in valid_types:
        errors.append(f"Invalid field type '{field['type']}'. Must be one of: {', '.join(valid_types)}")

    # Validate areas
    if "areas" in field:
        if not isinstance(field["areas"], list) or len(field["areas"]) == 0:
            errors.append("'areas' must be a non-empty list")
        else:
            for i, area in enumerate(field["areas"]):
                if not isinstance(area, dict):
                    errors.append(f"areas[{i}] must be a dictionary")
                    continue

                # Check required area properties
                required_area_props = ["x", "y", "w", "h", "page"]
                for prop in required_area_props:
                    if prop not in area:
                        errors.append(f"areas[{i}] missing required '{prop}' property")

                # Validate coordinate ranges
                if "x" in area and not (0 <= area["x"] <= 1):
                    errors.append(f"areas[{i}] x={area['x']} outside valid range [0, 1]")
                if "y" in area and not (0 <= area["y"] <= 1):
                    errors.append(f"areas[{i}] y={area['y']} outside valid range [0, 1]")
                if "w" in area and not (0 < area["w"] <= 1):
                    errors.append(f"areas[{i}] w={area['w']} outside valid range (0, 1]")
                if "h" in area and not (0 < area["h"] <= 1):
                    errors.append(f"areas[{i}] h={area['h']} outside valid range (0, 1]")

    return errors


def print_field_summary(fields: List[Dict[str, Any]]):
    """Print summary of fields to be created."""
    print(f"\n📋 Creating {len(fields)} field(s):")
    for i, field in enumerate(fields, 1):
        field_type = field.get("type", "unknown")
        field_name = field.get("name", "unnamed")
        num_areas = len(field.get("areas", []))
        required = "✓" if field.get("required", False) else " "
        print(f"   {i}. [{required}] {field_name} ({field_type}) - {num_areas} area(s)")


def main():
    """Main entry point for field creation."""
    parser = argparse.ArgumentParser(
        description="Create or update fields in DocuSeal templates via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Create a single signature field
    python field_creator.py --template-id "abc123" --field-json '{
      "name": "Client Signature",
      "type": "signature",
      "required": true,
      "areas": [{"x": 0.1, "y": 0.85, "w": 0.3, "h": 0.05, "page": 1}]
    }'

    # Create multiple fields from a JSON file
    python field_creator.py --template-id "abc123" --fields-file my_fields.json

    # Preview without creating
    python field_creator.py --template-id "abc123" --field-json '...' --dry-run

Environment Variables:
    DOCUSEAL_URL       Base URL of DocuSeal instance (e.g., https://docuseal.example.com)
    DOCUSEAL_API_KEY   API key for authentication
        """
    )

    parser.add_argument("--template-id", required=True,
                       help="Template ID to update")
    parser.add_argument("--field-json", type=str,
                       help="Field configuration as JSON string")
    parser.add_argument("--fields-file", type=str,
                       help="Path to JSON file containing field configurations")
    parser.add_argument("--dry-run", action="store_true",
                       help="Validate configuration without making API call")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Show detailed output")

    args = parser.parse_args()

    # Validate input
    if not args.field_json and not args.fields_file:
        parser.error("Either --field-json or --fields-file must be provided")

    # Load field configuration(s)
    try:
        if args.field_json:
            field_data = json.loads(args.field_json)
            # Support both single field and list of fields
            fields = [field_data] if isinstance(field_data, dict) else field_data
        else:
            with open(args.fields_file, 'r') as f:
                field_data = json.load(f)
                # Support both single field and list of fields
                fields = [field_data] if isinstance(field_data, dict) else field_data

    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"❌ File not found: {args.fields_file}", file=sys.stderr)
        sys.exit(1)

    # Validate field configurations
    all_errors = []
    for i, field in enumerate(fields):
        errors = validate_field_config(field)
        if errors:
            all_errors.append(f"Field {i+1} ({field.get('name', 'unnamed')}):")
            all_errors.extend([f"  - {err}" for err in errors])

    if all_errors:
        print("❌ Field validation failed:", file=sys.stderr)
        for error in all_errors:
            print(f"   {error}", file=sys.stderr)
        sys.exit(1)

    # Show field summary
    if args.verbose or args.dry_run:
        print_field_summary(fields)

    # Dry run - validate only
    if args.dry_run:
        print("\n✅ Field configuration is valid (dry run mode, no API call made)")
        sys.exit(0)

    # Create fields via API
    try:
        client = DocuSealAPIClient()

        if args.verbose:
            print(f"\n🔧 Updating template {args.template_id}...")

        result = client.create_fields(args.template_id, fields)

        print("\n✅ Fields created successfully!")

        if args.verbose:
            print("\n📄 API Response:")
            print(json.dumps(result, indent=2))

        sys.exit(0)

    except ValueError as e:
        print(f"❌ Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except requests.HTTPError as e:
        print(f"❌ API request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
