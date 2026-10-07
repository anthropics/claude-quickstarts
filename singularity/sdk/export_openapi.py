"""
Export the Singularity OpenAPI schema to a JSON file.

Usage:
    python -m sdk.export_openapi [output.json]

The resulting schema can be fed to openapi-generator / openapi-typescript to
generate a fully-typed client in any language.
"""

from __future__ import annotations

import json
import sys

from api.main import app
from sdk import export_openapi


def main() -> None:
    out = sys.argv[1] if len(sys.argv) > 1 else "openapi.json"
    schema = export_openapi(app)
    with open(out, "w") as f:
        json.dump(schema, f, indent=2)
    print(f"wrote {out} — {len(schema['paths'])} paths, "
          f"version {schema['info']['version']}")


if __name__ == "__main__":
    main()
