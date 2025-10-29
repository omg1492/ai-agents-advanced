"""Verification script for OpenTelemetry Baggage implementation.

Checks that all services have:
1. BaggageSpanProcessor class (not ContextAttributeSpanProcessor)
2. Baggage usage in middleware (baggage.set_baggage / baggage.get_baggage)
3. Proper imports (from opentelemetry import baggage)
"""

import os
from pathlib import Path
import sys

# Services to check
SERVICES = [
    ("DreamFarm Agent", "agents/dreamfarm-agent/src"),
    ("Chef Agent", "agents/chef-agent/src"),
    ("API Stock", "tools/api_stock"),
    ("MCP Visualization", "tools/mcp_visualization_generator"),
    ("MCP Chef Services", "tools/mcp_chef_services"),
    ("MCP Farmer Tools", "tools/mcp_public_farmer_tools"),
]

def check_file(filepath: Path, checks: dict) -> tuple[bool, list[str]]:
    """Check a file for expected patterns."""
    if not filepath.exists():
        return False, [f"File not found: {filepath}"]
    
    content = filepath.read_text(encoding='utf-8')
    errors = []
    
    for check_name, pattern in checks.items():
        if pattern not in content:
            errors.append(f"Missing: {check_name}")
    
    return len(errors) == 0, errors

def main():
    print("OpenTelemetry Baggage Implementation Verification")
    print("=" * 70)
    
    all_passed = True
    
    for service_name, service_path in SERVICES:
        print(f"\n{service_name}")
        print("-" * 70)
        
        base_path = Path(service_path)
        
        # Check otel_tracing.py
        if service_path.startswith("tools/api_stock"):
            tracing_file = base_path / "utils" / "otel_tracing.py"
        elif service_path.startswith("tools/"):
            tracing_file = base_path / "utils" / "otel_tracing.py"
        else:
            tracing_file = base_path / "utils" / "otel_tracing.py"
        
        tracing_checks = {
            "BaggageSpanProcessor class": "class BaggageSpanProcessor:",
            "baggage import": "from opentelemetry import baggage",
            "baggage.get_baggage call": "baggage.get_baggage(",
            "BAGGAGE_KEYS list": "BAGGAGE_KEYS = [",
            "Langfuse user.id": '"user.id"',
            "Langfuse session.id": '"session.id"',
        }
        
        passed, errors = check_file(tracing_file, tracing_checks)
        if passed:
            print(f"✅ {tracing_file.name}: All checks passed")
        else:
            print(f"❌ {tracing_file.name}: FAILED")
            for error in errors:
                print(f"   - {error}")
            all_passed = False
        
        # Check main.py middleware (only for services with FastAPI)
        if service_path.startswith("agents/") or service_path == "tools/api_stock":
            if service_path.startswith("agents/"):
                main_file = base_path / "main.py"
            else:
                main_file = base_path / "main.py"
            
            # DreamFarm Agent is origin service (only sets baggage)
            # Other services inherit baggage (get + set)
            if "dreamfarm" in service_name.lower():
                middleware_checks = {
                    "baggage import": "from opentelemetry import baggage",
                    "baggage.set_baggage": "baggage.set_baggage(",
                }
            else:
                middleware_checks = {
                    "baggage import": "from opentelemetry import baggage",
                    "baggage.set_baggage": "baggage.set_baggage(",
                    "baggage.get_baggage": "baggage.get_baggage(",
                }
            
            passed, errors = check_file(main_file, middleware_checks)
            if passed:
                print(f"✅ {main_file.name}: All checks passed")
            else:
                print(f"❌ {main_file.name}: FAILED")
                for error in errors:
                    print(f"   - {error}")
                all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✅ All services passed verification!")
        return 0
    else:
        print("❌ Some services failed verification. See errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
