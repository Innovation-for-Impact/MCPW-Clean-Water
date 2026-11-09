"""Generate TypeScript types from the OpenAPI schema.

Usage:
    python -m scripts.generate_types [--output shared/api-types.ts]

Reads the FastAPI app's OpenAPI schema and produces TypeScript interfaces
for all request/response models. This keeps frontend types in sync with
the backend without manual duplication.
"""

import argparse
import json
from pathlib import Path


def _ts_type(schema: dict, schemas: dict) -> str:
    """Convert a JSON Schema type to a TypeScript type string."""
    if "$ref" in schema:
        ref_name = schema["$ref"].split("/")[-1]
        return ref_name

    if "allOf" in schema:
        parts = [_ts_type(s, schemas) for s in schema["allOf"]]
        return " & ".join(parts)

    if "anyOf" in schema:
        parts = []
        has_null = False
        for s in schema["anyOf"]:
            if s.get("type") == "null":
                has_null = True
            else:
                parts.append(_ts_type(s, schemas))
        result = " | ".join(parts) if len(parts) > 1 else parts[0] if parts else "unknown"
        if has_null:
            result += " | null"
        return result

    schema_type = schema.get("type")

    if schema_type == "array":
        items = schema.get("items", {})
        return f"{_ts_type(items, schemas)}[]"

    if schema_type == "object":
        props = schema.get("properties")
        if props:
            return _inline_object(schema, schemas)
        additional = schema.get("additionalProperties")
        if additional and isinstance(additional, dict):
            return f"Record<string, {_ts_type(additional, schemas)}>"
        return "Record<string, unknown>"

    type_map = {
        "string": "string",
        "integer": "number",
        "number": "number",
        "boolean": "boolean",
        "null": "null",
    }

    if schema_type in type_map:
        # Check for enum
        if "enum" in schema:
            return " | ".join(f'"{v}"' for v in schema["enum"])
        # Check for format
        fmt = schema.get("format")
        if fmt in ("date-time", "date", "uuid"):
            return "string"
        return type_map[schema_type]

    return "unknown"


def _inline_object(schema: dict, schemas: dict) -> str:
    """Build an inline TypeScript object type."""
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    lines = []
    for name, prop_schema in props.items():
        optional = "" if name in required else "?"
        ts = _ts_type(prop_schema, schemas)
        lines.append(f"  {name}{optional}: {ts};")
    return "{\n" + "\n".join(lines) + "\n}"


def generate_interfaces(openapi: dict) -> str:
    """Generate TypeScript interfaces from OpenAPI components/schemas."""
    schemas = openapi.get("components", {}).get("schemas", {})
    lines = [
        "// Auto-generated from OpenAPI schema — do not edit manually.",
        f"// Generated from openapi.json ({len(schemas)} schemas)",
        "",
    ]

    for name, schema in schemas.items():
        # Skip internal/validation schemas
        if name.startswith("HTTPValidation") or name == "ValidationError":
            continue

        props = schema.get("properties", {})
        required = set(schema.get("required", []))

        if schema.get("enum"):
            # Enum type
            values = " | ".join(f'"{v}"' for v in schema["enum"])
            lines.append(f"export type {name} = {values};")
            lines.append("")
            continue

        if not props:
            # Type alias
            ts = _ts_type(schema, schemas)
            lines.append(f"export type {name} = {ts};")
            lines.append("")
            continue

        # Interface
        lines.append(f"export interface {name} {{")
        for prop_name, prop_schema in props.items():
            optional = "" if prop_name in required else "?"
            ts = _ts_type(prop_schema, schemas)
            desc = prop_schema.get("description")
            if desc:
                lines.append(f"  /** {desc} */")
            lines.append(f"  {prop_name}{optional}: {ts};")
        lines.append("}")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate TypeScript types from OpenAPI schema")
    parser.add_argument("--output", "-o", default="shared/api-types.ts", help="Output .ts file path")
    parser.add_argument("--openapi", default=None, help="Path to openapi.json (default: generate from app)")
    args = parser.parse_args()

    if args.openapi:
        openapi = json.loads(Path(args.openapi).read_text())
    else:
        # Generate from the live app
        import os

        os.environ.setdefault("SECRET_KEY", "generate-types")
        os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///")
        from src.api.main import app

        openapi = app.openapi()

    ts_content = generate_interfaces(openapi)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ts_content)
    print(f"Generated {output_path} ({len(openapi.get('components', {}).get('schemas', {}))} schemas)")


if __name__ == "__main__":
    main()
