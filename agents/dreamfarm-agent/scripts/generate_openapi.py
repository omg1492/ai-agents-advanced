#!/usr/bin/env python3
"""Generate OpenAPI specification file from FastAPI application."""

import json
import sys
from pathlib import Path

# Add src to path to import the app
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import app


def generate_openapi_spec():
    """Generate and save OpenAPI specification to file."""
    # Get the OpenAPI schema
    openapi_schema = app.openapi()
    
    # Create output directory if it doesn't exist
    output_dir = Path(__file__).parent.parent / "docs"
    output_dir.mkdir(exist_ok=True)
    
    # Save as JSON
    json_file = output_dir / "openapi.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2, ensure_ascii=False)
    
    print(f"OpenAPI specification saved to: {json_file}")
    
    # Also save as YAML (optional)
    try:
        import yaml
        yaml_file = output_dir / "openapi.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(openapi_schema, f, default_flow_style=False, allow_unicode=True)
        print(f"OpenAPI specification also saved as YAML to: {yaml_file}")
    except ImportError:
        print("PyYAML not installed - skipping YAML export")
        print("Install with: uv add pyyaml")


if __name__ == "__main__":
    generate_openapi_spec()
