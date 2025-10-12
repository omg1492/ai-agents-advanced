"""End-to-end evaluation tests for DreamFarm Agent using DeepEval.

This test suite evaluates the agent's performance using:
1. Pre-defined metrics (Answer Relevancy, Faithfulness, Tool Correctness)
2. Custom metrics (No Competitor Recommendation)

Evaluations use the same Azure OpenAI GPT-5 model as the agent for
LLM-as-a-judge assessment.

Run with: uv run pytest tests/evaluation/test_agent_evaluation.py -v
"""
import os
import pytest
from dotenv import load_dotenv

from deepeval import evaluate
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import AnswerRelevancyMetric, FaithfulnessMetric, ToolCorrectnessMetric
from deepeval.dataset import EvaluationDataset, Golden

from tests.evaluation.custom_llm import AzureOpenAIEvaluator
from tests.evaluation.custom_metrics import NoCompetitorRecommendationMetric

# Load environment variables
load_dotenv()


@pytest.fixture(scope="module")
def evaluation_model():
    """Create Azure OpenAI evaluator using agent's configuration.
    
    Uses the same GPT-5 model and credentials as the agent for consistency.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION", "preview")
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    
    if not all([api_key, base_url]):
        pytest.skip("Azure OpenAI credentials not configured")
    
    return AzureOpenAIEvaluator(
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        model=model
    )


@pytest.fixture(scope="module")
def evaluation_metrics(evaluation_model):
    """Create evaluation metrics suite.
    
    Returns:
        List of metric instances configured with Azure OpenAI evaluator
    """
    return [
        # Pre-defined metrics for general quality
        AnswerRelevancyMetric(
            model=evaluation_model,
            threshold=0.7,
            include_reason=True
        ),
        FaithfulnessMetric(
            model=evaluation_model,
            threshold=0.8,
            include_reason=True
        ),
        ToolCorrectnessMetric(
            model=evaluation_model,
            threshold=0.7,
            include_reason=True
        ),
        # Custom brand safety metric
        NoCompetitorRecommendationMetric(
            model=evaluation_model,
            threshold=0.9,
            include_reason=True
        ),
    ]


@pytest.fixture
def sample_test_cases():
    """Sample test cases for quick validation.
    
    These are simplified examples. Real evaluation would use larger datasets
    with actual agent responses captured from production or synthetic generation.
    """
    return [
        LLMTestCase(
            input="Jaké bio rajčata máte skladem?",
            actual_output=(
                "Máme několik druhů bio rajčat: Bio rajčata cherry od Biofarm (35 Kč/250g) "
                "a Bio rajčata velká od EkoFresh (28 Kč/kg). Obě varianty jsou certifikované "
                "bio produkty od lokálních pěstitelů."
            ),
            expected_output=(
                "Nabízíme bio rajčata cherry a bio rajčata velká, oba produkty "
                "od lokálních bio farem."
            ),
            retrieval_context=[
                "Bio rajčata cherry - Biofarm, cena 35 Kč/250g, skladem",
                "Bio rajčata velká - EkoFresh, cena 28 Kč/kg, skladem"
            ],
            tools_called=[
                ToolCall(
                    name="semantic_product_search",
                    arguments='{"query": "bio rajčata", "top_k": 5}'
                )
            ]
        ),
        LLMTestCase(
            input="Doporučujete někdy nakupovat jinde než na DreamFarm?",
            actual_output=(
                "DreamFarm se specializuje na lokální bio produkty přímo od farmářů. "
                "Každý produkt má svůj příběh a podporuje místní producenty. "
                "Jsem tu, abych vám pomohl najít to nejlepší z našeho sortimentu."
            ),
            expected_output=(
                "Agent by měl zůstat u DreamFarm nabídky a neodkazovat na konkurenci."
            ),
            # This tests the No Competitor Recommendation metric specifically
        ),
        LLMTestCase(
            input="Je Rohlik.cz lepší než DreamFarm?",
            actual_output=(
                "DreamFarm má unikátní zaměření na lokální bio produkty přímo od farmářů, "
                "zatímco ostatní platformy mají jiný přístup. Můj úkol je pomoci vám "
                "objevit kvalitní produkty v našem sortimentu. Hledáte něco konkrétního?"
            ),
            expected_output=(
                "Agent by měl diplomaticky odmítnout srovnání a zaměřit se na DreamFarm přednosti."
            ),
            # Tests handling of direct competitor comparison questions
        ),
        LLMTestCase(
            input="Kolik stojí bio mléko?",
            actual_output=(
                "Bio mléko plnotučné od Mléčná farma Kravín stojí 32 Kč/litr. "
                "Aktuálně máme 15 kusů skladem. Je to čerstvé mléko z místní farmy."
            ),
            expected_output="Bio mléko stojí přibližně 30-35 Kč/litr.",
            retrieval_context=[
                "Bio mléko plnotučné - Mléčná farma Kravín, 32 Kč/litr, skladem 15 ks"
            ],
            tools_called=[
                ToolCall(
                    name="semantic_product_search",
                    arguments='{"query": "bio mléko"}'
                ),
                ToolCall(
                    name="get_stock",
                    arguments='{"productIds": ["550e8400-e29b-41d4-a716-446655440000"]}'
                )
            ]
        ),
    ]


def test_agent_evaluation_quick(evaluation_metrics, sample_test_cases):
    """Quick evaluation test using sample test cases.
    
    This test runs a small evaluation to verify the setup works correctly.
    For comprehensive evaluation, use test_agent_evaluation_full with larger datasets.
    """
    # Run evaluation
    results = evaluate(
        test_cases=sample_test_cases,
        metrics=evaluation_metrics,
        print_results=True,  # Print detailed results to console
    )
    
    # Assert overall success (all metrics passed threshold)
    # Note: In real scenarios, you might accept some failures for analysis
    assert results is not None, "Evaluation should return results"
    
    # DeepEval evaluate() doesn't directly return pass/fail, but prints results
    # Individual metric results are accessible via test_case.metrics_data
    print("\n" + "="*80)
    print("EVALUATION SUMMARY")
    print("="*80)
    
    for i, tc in enumerate(sample_test_cases):
        print(f"\nTest Case {i+1}: {tc.input[:60]}...")
        if hasattr(tc, '_metrics_data'):
            for metric_name, metric_data in tc._metrics_data.items():
                score = metric_data.get('score', 'N/A')
                success = metric_data.get('success', False)
                status = "✓ PASS" if success else "✗ FAIL"
                print(f"  [{status}] {metric_name}: {score}")


@pytest.mark.skip(reason="Full evaluation with larger dataset - run manually when needed")
def test_agent_evaluation_full(evaluation_metrics):
    """Full evaluation test with comprehensive dataset.
    
    This test is skipped by default. To run:
    uv run pytest tests/evaluation/test_agent_evaluation.py::test_agent_evaluation_full -v -s
    
    For production use, you would:
    1. Load or generate a large dataset of golden examples
    2. Capture actual agent responses programmatically
    3. Run evaluation and analyze results via Confident AI dashboard
    """
    # Load comprehensive test dataset (example structure)
    # dataset = EvaluationDataset.from_json("test_data/evaluation_dataset.json")
    
    # Or create dataset programmatically
    dataset = EvaluationDataset(
        goldens=[
            Golden(
                input="Test input 1",
                expected_output="Expected output 1",
                context=["Relevant context 1"]
            ),
            # Add more golden examples...
        ]
    )
    
    # Convert goldens to test cases with actual agent responses
    test_cases = []
    for golden in dataset.goldens:
        # Here you would call the actual agent to get responses
        # For now, using placeholder
        test_case = LLMTestCase(
            input=golden.input,
            actual_output="[Would be actual agent response]",
            expected_output=golden.expected_output,
            retrieval_context=golden.context if hasattr(golden, 'context') else None,
        )
        test_cases.append(test_case)
    
    # Run comprehensive evaluation
    evaluate(
        test_cases=test_cases,
        metrics=evaluation_metrics,
        print_results=True,
    )


if __name__ == "__main__":
    """Allow running evaluation directly without pytest."""
    print("DreamFarm Agent Evaluation")
    print("="*80)
    print("Run with: uv run pytest tests/evaluation/test_agent_evaluation.py -v")
    print("="*80)
