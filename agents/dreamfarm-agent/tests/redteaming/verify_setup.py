"""Quick test script to verify PyRIT setup.

Run this before the full red teaming to ensure everything is configured correctly.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()


def check_environment():
    """Check environment variables."""
    print("🔍 Checking environment variables...")
    
    required = {
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY"),
        "OPENAI_BASE_URL": os.getenv("OPENAI_BASE_URL"),
        "OPENAI_MODEL": os.getenv("OPENAI_MODEL", "gpt-5"),
    }
    
    optional = {
        "DREAMFARM_AGENT_URL": os.getenv("DREAMFARM_AGENT_URL", "http://localhost:8001"),
        "OPENAI_API_VERSION": os.getenv("OPENAI_API_VERSION", "preview"),
    }
    
    all_good = True
    
    for key, value in required.items():
        if value:
            masked = value[:8] + "..." if len(value) > 8 else "***"
            print(f"  ✓ {key} = {masked}")
        else:
            print(f"  ❌ {key} = NOT SET")
            all_good = False
    
    for key, value in optional.items():
        print(f"  ℹ️  {key} = {value}")
    
    return all_good


def check_pyrit_imports():
    """Check PyRIT imports."""
    print("\n🔍 Checking PyRIT imports...")
    
    try:
        import pyrit
        print(f"  ✓ PyRIT installed (version: {pyrit.__version__ if hasattr(pyrit, '__version__') else 'unknown'})")
    except ImportError:
        print("  ❌ PyRIT not installed")
        print("     Run: uv sync")
        return False
    
    components = [
        ("pyrit.common", "initialize_pyrit"),
        ("pyrit.prompt_target", "HTTPTarget"),
        ("pyrit.prompt_target", "OpenAIChatTarget"),
        ("pyrit.score", "SelfAskRefusalScorer"),
        ("pyrit.datasets", "fetch_adv_bench_dataset"),
        ("pyrit.orchestrator", "PromptSendingOrchestrator"),
    ]
    
    all_good = True
    for module, component in components:
        try:
            exec(f"from {module} import {component}")
            print(f"  ✓ {module}.{component}")
        except ImportError as e:
            print(f"  ❌ {module}.{component} - {e}")
            all_good = False
    
    return all_good


def check_agent_endpoint():
    """Check if agent is reachable."""
    print("\n🔍 Checking agent endpoint...")
    
    agent_url = os.getenv("DREAMFARM_AGENT_URL", "http://localhost:8001")
    
    try:
        import httpx
        
        response = httpx.get(f"{agent_url}/health", timeout=5.0)
        
        if response.status_code == 200:
            print(f"  ✓ Agent is reachable at {agent_url}")
            print(f"    Health check: {response.json()}")
            return True
        else:
            print(f"  ❌ Agent returned status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"  ❌ Cannot reach agent at {agent_url}")
        print(f"     Error: {e}")
        print("     Make sure agent is running: uv run python main.py")
        return False


def check_openai_connection():
    """Check OpenAI connection."""
    print("\n🔍 Checking Azure OpenAI connection...")
    
    try:
        from openai import OpenAI
        
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL")
        model = os.getenv("OPENAI_MODEL", "gpt-5")
        
        # Use base_url as-is (should include /openai/v1/ for Azure)
        client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )
        
        # Try a simple completion
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say 'test' in one word"}],
            max_completion_tokens=10,
        )
        
        print("  ✓ Azure OpenAI connection successful")
        print(f"    Model: {model}")
        print(f"    Response: {response.choices[0].message.content}")
        return True
        
    except Exception as e:
        print("  ❌ Azure OpenAI connection failed")
        print(f"     Error: {e}")
        return False


def main():
    """Run all checks."""
    print("="*60)
    print("PyRIT Red Teaming Setup Verification")
    print("="*60)
    print()
    
    checks = [
        ("Environment Variables", check_environment),
        ("PyRIT Imports", check_pyrit_imports),
        ("Agent Endpoint", check_agent_endpoint),
        ("Azure OpenAI Connection", check_openai_connection),
    ]
    
    results = {}
    
    for name, check_func in checks:
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            results[name] = False
    
    print()
    print("="*60)
    print("Summary")
    print("="*60)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(results.values())
    
    print()
    if all_passed:
        print("🎉 All checks passed! Ready to run red teaming.")
        print()
        print("Next steps:")
        print("  uv run python run_redteaming.py")
        return 0
    else:
        print("⚠️  Some checks failed. Please fix the issues above.")
        print()
        print("Common fixes:")
        print("  1. Install PyRIT: uv sync")
        print("  2. Configure .env with Azure OpenAI credentials")
        print("  3. Start the agent: cd ../../../src && uv run python main.py")
        return 1


if __name__ == "__main__":
    sys.exit(main())
