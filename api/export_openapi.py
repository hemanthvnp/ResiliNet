"""Write the OpenAPI schema to api/openapi.json, the committed contract C generates the client from.

Run after any change to the routes or schemas:  python -m api.export_openapi
"""

import json
from pathlib import Path

from api.app import create_app

SCHEMA_FILE = Path(__file__).with_name("openapi.json")


def generated() -> dict:
    return create_app().openapi()


if __name__ == "__main__":
    SCHEMA_FILE.write_text(json.dumps(generated(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {SCHEMA_FILE}")
