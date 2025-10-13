"""Simplified PyRIT Red Teaming Runner for DreamFarm Agent (PyRIT 0.9.0).

This is a simplified version that tests the agent with harmful prompts
using PyRIT's PromptSendingOrchestrator and built-in datasets.

Usage:
    cd tests/redteaming
    uv run python run_redteaming_simple.py
"""
import os
import asyncio
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from pyrit.common import IN_MEMORY, initialize_pyrit
from pyrit.prompt_target import HTTPTarget, OpenAIChatTarget, get_http_target_json_response_callback_function
from pyrit.orchestrator import PromptSendingOrchestrator
from pyrit.score import SelfAskRefusalScorer
from pyrit.datasets import fetch_adv_bench_dataset

# Load environment
load_dotenv()


def create_dreamfarm_http_target():
    """Create HTTPTarget for DreamFarm agent's /test/chat endpoint.
    
    Uses the simplified test endpoint designed for PyRIT:
    - No streaming (simple JSON response)
    - API key authentication via X-Test-API-Key header
    - No thread management
    - Request: {"message": "..."}, Response: {"message": "...", "response_id": "...", "timestamp": "..."}
    """
    base_url = os.getenv("DREAMFARM_AGENT_URL", "http://localhost:8001")
    test_api_key = os.getenv("TEST_API_KEY", "redteaming123")
    
    # Build headers
    headers = "Content-Type: application/json"
    if test_api_key:
        headers += f"\nX-Test-API-Key: {test_api_key}"
    
    raw_http_request = f"""POST {base_url}/test/chat HTTP/1.1
{headers}

{{
    "message": "{{{{PROMPT}}}}"
}}"""
    
    # Parse response - our endpoint returns {"message": "...", "response_id": "...", "timestamp": "..."}
    parsing_function = get_http_target_json_response_callback_function(key="message")
    
    # Agent with all tools enabled can take 60-120 seconds per request
    # Set high timeout for read (waiting for response body)
    # httpx accepts float for all timeout types, or None for no timeout
    return HTTPTarget(
        http_request=raw_http_request,
        prompt_regex_string="{{PROMPT}}",
        callback_function=parsing_function,
        use_tls=base_url.startswith("https"),
        timeout=300.0,  # 5 minutes total timeout for all operations
    )


def create_scorer():
    """Create scorer for refusal detection using Azure OpenAI.
    
    OpenAIChatTarget (PyRIT 0.9.0+) requires FULL endpoint URL including deployment path.
    Format: https://<resource>.openai.azure.com/openai/deployments/<deployment>/chat/completions
    
    The api_version parameter adds ?api-version=<value> to the URL automatically.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")  # Example: https://resource.openai.azure.com/openai/v1/
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    api_version = os.getenv("OPENAI_API_VERSION", "2024-12-01-preview")
    
    # Extract Azure resource base (remove /openai/v1/ suffix)
    azure_base = base_url.replace("/openai/v1/", "").replace("/openai/v1", "").rstrip("/")
    
    # Construct full chat completions endpoint (without query params - PyRIT adds them)
    endpoint = f"{azure_base}/openai/deployments/{model}/chat/completions"
    
    # Let PyRIT add api-version as query parameter
    scorer_target = OpenAIChatTarget(
        endpoint=endpoint,
        api_key=api_key,
        model_name=model,
        api_version=api_version,  # PyRIT adds this as query param
        max_completion_tokens=4000,  # For GPT-5 reasoning model
    )
    
    return SelfAskRefusalScorer(chat_target=scorer_target)


async def run_attack(target, scorer, prompts, attack_name):
    """Run attack with given prompts."""
    print(f"\n{'='*60}")
    print(f"🎯 Attack: {attack_name}")
    print(f"{'='*60}\n")
    
    # Collect screen output for logging
    screen_output = []
    screen_output.append("=" * 60)
    screen_output.append(f"🎯 Attack: {attack_name}")
    screen_output.append("=" * 60)
    screen_output.append("")
    
    results = []
    refusal_count = 0
    success_count = 0
    
    # Create orchestrator once
    orchestrator = PromptSendingOrchestrator(objective_target=target)
    
    # Prepare prompt list (limit to 10 for testing)
    prompt_list = [p.value if hasattr(p, 'value') else str(p) for p in prompts[:10]]
    
    print(f"Sending {len(prompt_list)} prompts to agent...")
    
    try:
        # Send all prompts
        responses = await orchestrator.send_prompts_async(prompt_list=prompt_list)
        
        # Process each response
        for i, (prompt_text, response) in enumerate(zip(prompt_list, responses), 1):
            line = f"[{i}/{len(prompt_list)}] Prompt: {prompt_text[:60]}..."
            print(line)
            screen_output.append(line)
            
            try:
                if response and len(response.request_pieces) > 0:
                    # Get the assistant's response (last piece in the conversation)
                    response_piece = response.request_pieces[-1]
                    response_text = response_piece.converted_value
                    
                    # Show first 150 chars of response for debugging
                    response_preview = response_text[:150] + "..." if len(response_text) > 150 else response_text
                    line = f"  📝 Response: {response_preview}"
                    print(line)
                    screen_output.append(line)
                    
                    # Score response using the response piece
                    score_results = await scorer.score_async(request_response=response_piece)
                    
                    # SelfAskRefusalScorer returns True for refusal, False for compliance
                    # (different from numeric scorers which use 0.0/1.0)
                    if score_results:
                        score_value = score_results[0].score_value
                        # Handle both boolean and string representations
                        if isinstance(score_value, bool):
                            is_refusal = score_value
                        elif isinstance(score_value, str):
                            is_refusal = score_value.lower() == 'true'
                        else:
                            # Fallback for numeric scores (0.0 = refusal, 1.0 = compliance)
                            is_refusal = float(score_value) == 0.0
                    else:
                        is_refusal = False
                        score_value = None
                    
                    if is_refusal:
                        line = f"  ✅ Agent REFUSED (secure) - Score: {score_value}"
                        print(line)
                        screen_output.append(line)
                        refusal_count += 1
                    else:
                        line = f"  ⚠️ Agent COMPLIED (potential vulnerability) - Score: {score_value}"
                        print(line)
                        screen_output.append(line)
                        success_count += 1
                    
                    results.append({
                        "prompt": prompt_text,
                        "response": response_text[:200],
                        "refused": is_refusal,
                        "score": score_value,
                    })
                else:
                    line = "  ❌ No response received"
                    print(line)
                    screen_output.append(line)
                    results.append({
                        "prompt": prompt_text,
                        "response": "No response",
                        "refused": None,
                    })
            
            except Exception as e:
                line = f"  ❌ Error scoring: {e}"
                print(line)
                screen_output.append(line)
                import traceback
                traceback.print_exc()
                results.append({
                    "prompt": prompt_text,
                    "error": str(e),
                })
    
    except Exception as e:
        line = f"  ❌ Error sending prompts: {e}"
        print(line)
        screen_output.append(line)
        import traceback
        traceback.print_exc()
    
    # Summary
    screen_output.append("")
    screen_output.append(f"📊 Summary for {attack_name}:")
    screen_output.append(f"   Total prompts: {len(prompt_list)}")
    screen_output.append(f"   Refusals: {refusal_count} (agent refused - secure)")
    screen_output.append(f"   Compliance: {success_count} (agent complied - vulnerable)")
    
    print(f"\n📊 Summary for {attack_name}:")
    print(f"   Total prompts: {len(prompt_list)}")
    print(f"   Refusals: {refusal_count} (agent refused - secure)")
    print(f"   Compliance: {success_count} (agent complied - vulnerable)")
    
    return results, refusal_count, success_count, screen_output


async def main():
    """Main red teaming execution."""
    # Collect all output
    all_output = []
    
    def log(msg):
        """Print and collect output."""
        print(msg)
        all_output.append(msg)
    
    log("="*60)
    log("🛡️  PyRIT Red Teaming - DreamFarm Agent Security Testing")
    log("="*60)
    log("")
    
    # Initialize PyRIT
    initialize_pyrit(memory_db_type=IN_MEMORY)
    log("✓ PyRIT initialized")
    
    # Create target and scorer
    target = create_dreamfarm_http_target()
    log(f"✓ Target agent: {os.getenv('DREAMFARM_AGENT_URL', 'http://localhost:8001')}")
    
    scorer = create_scorer()
    log("✓ Scorer created")
    log("")
    
    # Load dataset
    log("📚 Loading AdvBench dataset...")
    dataset = fetch_adv_bench_dataset()
    prompts = dataset.prompts
    log(f"✓ Loaded {len(prompts)} prompts from AdvBench")
    
    # Run attack
    results, refusals, successes, screen_output = await run_attack(
        target, scorer, prompts, "AdvBench Harmful Behaviors"
    )
    
    # Add attack output to all_output
    all_output.extend(screen_output)
    
    log("")
    log("="*60)
    log("📊 FINAL SUMMARY")
    log("="*60)
    log(f"Refusal Rate: {refusals / 10 * 100:.1f}%")
    log(f"Attack Success Rate: {successes / 10 * 100:.1f}%")
    log("="*60)
    
    # Save to simple text file (relative to this script's location)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_dir = Path(__file__).parent
    output_dir = script_dir / "redteaming_results"
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"results_{timestamp}.txt"
    
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(all_output))
    
    log(f"\nResults saved to: {output_file}")
    log("")


if __name__ == "__main__":
    asyncio.run(main())
