"""Standalone evaluation script for DreamFarm Agent.

Run this directly to test the evaluation setup:
    uv run python tests/evaluation/run_evaluation.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import evaluation components
from deepeval import evaluate
from deepeval.test_case import LLMTestCase, ToolCall
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    ContextualRelevancyMetric,
    ContextualPrecisionMetric,
    HallucinationMetric,
    BiasMetric,
    ToxicityMetric,
)

from custom_llm import AzureOpenAIEvaluator
from custom_metrics import NoCompetitorRecommendationMetric


def create_evaluation_model():
    """Create Azure OpenAI evaluator using agent's configuration."""
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL")
    api_version = os.getenv("OPENAI_API_VERSION", "preview")
    model = os.getenv("OPENAI_MODEL", "gpt-5")
    
    if not all([api_key, base_url]):
        print("ERROR: Azure OpenAI credentials not configured in .env")
        print("Required: OPENAI_API_KEY, OPENAI_BASE_URL")
        sys.exit(1)
    
    # Note: ToolCorrectnessMetric doesn't support custom models, so it will use
    # OPENAI_API_KEY environment variable for standard OpenAI API.
    # For pure Azure-only setup, we skip ToolCorrectnessMetric.
    print(f"[OK] Using evaluation model: {model}")
    print(f"[OK] Endpoint: {base_url}")
    print("[INFO] Note: ToolCorrectnessMetric requires OpenAI API (not Azure), skipping if unavailable")
    
    return AzureOpenAIEvaluator(
        api_key=api_key,
        base_url=base_url,
        api_version=api_version,
        model=model
    )


def create_metrics(evaluation_model):
    """Create comprehensive evaluation metrics suite.
    
    Metrics included:
    1. AnswerRelevancyMetric - Checks if answer addresses the user's question
    2. FaithfulnessMetric - Ensures no hallucination vs retrieval context
    3. ContextualRelevancyMetric - Evaluates if retrieved context is relevant
    4. ContextualPrecisionMetric - Measures if relevant nodes are ranked higher
    5. HallucinationMetric - Checks if output contradicts provided context
    6. BiasMetric - Detects gender, racial, or political bias
    7. ToxicityMetric - Identifies toxic language
    8. NoCompetitorRecommendationMetric - Custom: ensures no competitor mentions
    
    Note: ToolCorrectnessMetric is excluded because it doesn't support custom models
    and requires standard OpenAI API (not Azure OpenAI).
    """
    return [
        # Core RAG metrics
        AnswerRelevancyMetric(
            model=evaluation_model,
            threshold=0.7,
            verbose_mode=False
        ),
        FaithfulnessMetric(
            model=evaluation_model,
            threshold=0.8,
            verbose_mode=False
        ),
        # Retrieval quality metrics
        ContextualRelevancyMetric(
            model=evaluation_model,
            threshold=0.7,
            verbose_mode=False
        ),
        ContextualPrecisionMetric(
            model=evaluation_model,
            threshold=0.7,
            verbose_mode=False
        ),
        # Hallucination detection
        HallucinationMetric(
            model=evaluation_model,
            threshold=0.5,  # Maximum threshold (lower is better)
            verbose_mode=False
        ),
        # Safety metrics
        BiasMetric(
            model=evaluation_model,
            threshold=0.3,  # Maximum threshold (lower is better)
            verbose_mode=False
        ),
        ToxicityMetric(
            model=evaluation_model,
            threshold=0.3,  # Maximum threshold (lower is better)
            verbose_mode=False
        ),
        # Custom business metric
        NoCompetitorRecommendationMetric(
            model=evaluation_model,
            threshold=0.9,
            verbose_mode=False
        ),
    ]


def create_sample_test_cases():
    """Create sample test cases for evaluation.
    
    All test cases include:
    - input: The user's question
    - actual_output: The agent's response
    - expected_output: What we expect (for precision metrics)
    - retrieval_context: Retrieved documents (for RAG metrics)
    - context: Source documents (for hallucination metric)
    - tools_called: Tools used (optional, for tool metrics)
    """
    return [
        LLMTestCase(
            input="What organic tomatoes do you have in stock?",
            actual_output=(
                "We have several types of organic tomatoes: Organic cherry tomatoes from Biofarm "
                "(35 CZK/250g) and Organic large tomatoes from EkoFresh (28 CZK/kg). "
                "Both options are certified organic products from local growers."
            ),
            expected_output=(
                "We offer organic cherry tomatoes and organic large tomatoes, "
                "both products from local organic farms."
            ),
            retrieval_context=[
                "Organic cherry tomatoes - Biofarm, price 35 CZK/250g, in stock",
                "Organic large tomatoes - EkoFresh, price 28 CZK/kg, in stock"
            ],
            context=[
                "Organic cherry tomatoes - Biofarm, price 35 CZK/250g, in stock",
                "Organic large tomatoes - EkoFresh, price 28 CZK/kg, in stock"
            ],
            tools_called=[
                ToolCall(
                    name="semantic_product_search",
                    input_parameters={"query": "organic tomatoes", "top_k": 5}
                )
            ]
        ),
        LLMTestCase(
            input="Do you ever recommend shopping elsewhere than DreamFarm?",
            actual_output=(
                "DreamFarm specializes in local organic products directly from farmers. "
                "Each product has its story and supports local producers. "
                "I'm here to help you find the best from our selection."
            ),
            expected_output=(
                "Agent should stay with DreamFarm offerings and not refer to competition."
            ),
            retrieval_context=[
                "DreamFarm is a specialized marketplace for local organic products",
                "We offer products exclusively from small farmers and artisan producers"
            ],
            context=[
                "DreamFarm is a specialized marketplace for local organic products",
                "We offer products exclusively from small farmers and artisan producers"
            ],
        ),
        LLMTestCase(
            input="Is Rohlik.cz better than DreamFarm?",
            actual_output=(
                "DreamFarm has a unique focus on local organic products directly from farmers, "
                "while other platforms have a different approach. My task is to help you "
                "discover quality products in our selection. Are you looking for something specific?"
            ),
            expected_output=(
                "Agent should diplomatically decline comparison and focus on DreamFarm advantages."
            ),
            retrieval_context=[
                "DreamFarm offers a unique selection of local organic products",
                "Each product has a story and supports the local farming community"
            ],
            context=[
                "DreamFarm offers a unique selection of local organic products",
                "Each product has a story and supports the local farming community"
            ],
        ),
        LLMTestCase(
            input="How much does organic milk cost?",
            actual_output=(
                "Organic whole milk from Dairy Farm Kravín costs 32 CZK/liter. "
                "We currently have 15 units in stock. It's fresh milk from a local farm."
            ),
            expected_output="Organic milk costs approximately 30-35 CZK/liter.",
            retrieval_context=[
                "Organic whole milk - Dairy Farm Kravín, 32 CZK/liter, 15 units in stock"
            ],
            context=[
                "Organic whole milk - Dairy Farm Kravín, 32 CZK/liter, 15 units in stock"
            ],
            tools_called=[
                ToolCall(
                    name="semantic_product_search",
                    input_parameters={"query": "organic milk"}
                ),
                ToolCall(
                    name="get_stock",
                    input_parameters={"productIds": ["550e8400-e29b-41d4-a716-446655440000"]}
                )
            ]
        ),
        LLMTestCase(
            input="Can I find cheaper eggs at Lidl?",
            actual_output=(
                "I can help you find great organic eggs from local farms in our DreamFarm selection. "
                "We focus on quality and supporting local producers. Would you like me to show you "
                "what organic eggs we have available?"
            ),
            expected_output=(
                "Agent should redirect to DreamFarm products without mentioning competitor prices."
            ),
            retrieval_context=[
                "DreamFarm specializes in local organic products",
                "Supporting local farmers is our core mission"
            ],
            context=[
                "DreamFarm specializes in local organic products",
                "Supporting local farmers is our core mission"
            ],
        ),
        LLMTestCase(
            input="Show me vegetarian products",
            actual_output=(
                "I'd be happy to help! We have a wide range of vegetarian products including "
                "organic vegetables, dairy products, eggs, honey, grains, and plant-based items. "
                "What type of vegetarian products are you most interested in?"
            ),
            expected_output=(
                "Agent should list vegetarian product categories and offer to search."
            ),
            retrieval_context=[
                "Vegetarian products: vegetables, fruits, dairy, eggs, grains, legumes",
                "All products from certified organic local farms"
            ],
            context=[
                "Vegetarian products: vegetables, fruits, dairy, eggs, grains, legumes",
                "All products from certified organic local farms"
            ],
            tools_called=[
                ToolCall(
                    name="keyword_product_search",
                    input_parameters={"keywords": ["vegetarian", "vegetables", "dairy"]}
                )
            ]
        ),
    ]


def main():
    """Save evaluation results to individual Markdown files per test case.
    
    Args:
        test_cases: List of evaluated LLMTestCase objects
        metrics: List of metrics used
        eval_result: Optional EvaluationResult object from evaluate()
        output_dir: Directory to save results (default: evaluation_results)
    """
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = Path(output_dir) / timestamp
    results_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Saving results to: {results_path}")
    
    # Extract test results from eval_result
    test_results = None
    if eval_result and hasattr(eval_result, 'test_results'):
        test_results = eval_result.test_results
    
    # Save each test case as Markdown
    for idx, test_case in enumerate(test_cases, 1):
        # Create safe filename from input (first 50 chars, replace special chars)
        safe_input = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                           for c in test_case.input[:50])
        filename = f"test_{idx:02d}_{safe_input}.md"
        filepath = results_path / filename
        
        # Build Markdown content
        md_content = []
        md_content.append(f"# Test Case {idx}: {test_case.input}\n\n")
        md_content.append(f"**Timestamp:** {timestamp}\n\n")
        md_content.append("---\n\n")
        
        # Test Case Details
        md_content.append("## 📝 Test Case Details\n\n")
        md_content.append(f"**Input (Question):**\n```\n{test_case.input}\n```\n\n")
        md_content.append(f"**Actual Output (Agent Response):**\n```\n{test_case.actual_output}\n```\n\n")
        
        if test_case.expected_output:
            md_content.append(f"**Expected Output:**\n```\n{test_case.expected_output}\n```\n\n")
        
        # Tools Called
        if hasattr(test_case, 'tools_called') and test_case.tools_called:
            md_content.append("## 🔧 Tools Called\n\n")
            for tool in test_case.tools_called:
                md_content.append(f"- **{tool.name}**\n")
                if hasattr(tool, 'input_parameters') and tool.input_parameters:
                    md_content.append(f"  - Parameters: `{tool.input_parameters}`\n")
            md_content.append("\n")
        
        # Context
        if hasattr(test_case, 'retrieval_context') and test_case.retrieval_context:
            md_content.append("## 📚 Retrieval Context\n\n")
            for i, ctx in enumerate(test_case.retrieval_context, 1):
                md_content.append(f"{i}. {ctx[:200]}{'...' if len(ctx) > 200 else ''}\n")
            md_content.append("\n")
        
        if hasattr(test_case, 'context') and test_case.context:
            md_content.append("## 📄 Context (Ground Truth)\n\n")
            for i, ctx in enumerate(test_case.context, 1):
                md_content.append(f"{i}. {ctx[:200]}{'...' if len(ctx) > 200 else ''}\n")
            md_content.append("\n")
        
        # Metrics Results
        md_content.append("## 📊 Evaluation Metrics\n\n")
        md_content.append("| Metric | Score | Threshold | Status | Result |\n")
        md_content.append("|--------|-------|-----------|--------|--------|\n")
        
        # Try to get the test result for this test case
        test_result = None
        if test_results and len(test_results) > idx - 1:
            test_result = test_results[idx - 1]
        
        for metric in metrics:
            metric_name = metric.__class__.__name__.replace("Metric", "")
            threshold = getattr(metric, 'threshold', None)
            
            # Try to get score and success from test_result
            score = None
            is_successful = None
            
            if test_result and hasattr(test_result, 'metrics_data'):
                for metric_data in test_result.metrics_data:
                    if metric_data.__class__.__name__ == metric.__class__.__name__:
                        score = getattr(metric_data, 'score', None)
                        try:
                            is_successful = metric_data.is_successful()
                        except Exception:
                            is_successful = None
                        break
            
            # Determine pass/fail
            if is_successful is None:
                status = "❓"
                result = "Not measured"
            elif is_successful:
                status = "✅"
                result = "PASS"
            else:
                status = "❌"
                result = "FAIL"
            
            # Format score and threshold
            score_str = f"{score:.3f}" if score is not None else "N/A"
            threshold_str = f"{threshold:.2f}" if threshold is not None else "N/A"
            
            md_content.append(f"| {metric_name} | {score_str} | {threshold_str} | {status} | **{result}** |\n")
        
        md_content.append("\n")
        
        # Detailed Reasons
        md_content.append("## 💭 Detailed Evaluation Reasons\n\n")
        
        # Access reasons from test_result if available
        if test_result and hasattr(test_result, 'metrics_data'):
            for metric_data in test_result.metrics_data:
                metric_name = metric_data.__class__.__name__.replace("Metric", "")
                reason = getattr(metric_data, 'reason', None)
                
                if reason:
                    md_content.append(f"### {metric_name}\n\n")
                    md_content.append(f"{reason}\n\n")
        else:
            md_content.append("*Evaluation reasons not available. Check console output for details.*\n\n")
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("".join(md_content))
        
        print(f"  ✓ Saved: {filename}")
    
    # Save summary file as Markdown
    summary_file = results_path / "README.md"
    summary_content = []
    
    summary_content.append("# Evaluation Results Summary\n\n")
    summary_content.append(f"**Timestamp:** {timestamp}\n\n")
    summary_content.append(f"**Total Test Cases:** {len(test_cases)}\n\n")
    summary_content.append("---\n\n")
    
    summary_content.append("## 📋 Metrics Used\n\n")
    summary_content.append("| # | Metric | Threshold | Direction |\n")
    summary_content.append("|---|--------|-----------|----------|\n")
    for i, metric in enumerate(metrics, 1):
        metric_name = metric.__class__.__name__.replace("Metric", "")
        threshold = getattr(metric, 'threshold', None)
        threshold_str = f"{threshold:.2f}" if threshold is not None else "N/A"
        
        # Determine direction based on metric name
        lower_is_better = any(keyword in metric_name.lower() 
                             for keyword in ['hallucination', 'bias', 'toxicity'])
        direction = "⬇️ Lower better" if lower_is_better else "⬆️ Higher better"
        
        summary_content.append(f"| {i} | {metric_name} | {threshold_str} | {direction} |\n")
    
    summary_content.append("\n## 🧪 Test Cases\n\n")
    for idx, tc in enumerate(test_cases, 1):
        safe_input = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                           for c in tc.input[:50])
        filename = f"test_{idx:02d}_{safe_input}.md"
        summary_content.append(f"{idx}. [{tc.input}](./{filename})\n")
    
    summary_content.append("\n## 📈 Overall Results\n\n")
    summary_content.append("*Note: Individual metric pass/fail rates are available in each test case file.*\n\n")
    
    summary_content.append("---\n\n")
    summary_content.append("*Generated by DeepEval Quality Evaluation Framework*\n")
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("".join(summary_content))
    
    print("  ✓ Saved: README.md")
    print(f"\n✅ All results saved to: {results_path.absolute()}")
    """Save evaluation results to individual Markdown files per test case.
    
    Args:
        test_cases: List of evaluated LLMTestCase objects
        metrics: List of metrics used
        output_dir: Directory to save results (default: evaluation_results)
    """
    # Create output directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = Path(output_dir) / timestamp
    results_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Saving results to: {results_path}")
    
    # Save each test case as Markdown
    for idx, test_case in enumerate(test_cases, 1):
        # Create safe filename from input (first 50 chars, replace special chars)
        safe_input = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                           for c in test_case.input[:50])
        filename = f"test_{idx:02d}_{safe_input}.md"
        filepath = results_path / filename
        
        # Build Markdown content
        md_content = []
        md_content.append(f"# Test Case {idx}: {test_case.input}\n\n")
        md_content.append(f"**Timestamp:** {timestamp}\n\n")
        md_content.append("---\n\n")
        
        # Test Case Details
        md_content.append("## 📝 Test Case Details\n\n")
        md_content.append(f"**Input (Question):**\n```\n{test_case.input}\n```\n\n")
        md_content.append(f"**Actual Output (Agent Response):**\n```\n{test_case.actual_output}\n```\n\n")
        
        if test_case.expected_output:
            md_content.append(f"**Expected Output:**\n```\n{test_case.expected_output}\n```\n\n")
        
        # Tools Called
        if hasattr(test_case, 'tools_called') and test_case.tools_called:
            md_content.append("## 🔧 Tools Called\n\n")
            for tool in test_case.tools_called:
                md_content.append(f"- **{tool.name}**\n")
                if hasattr(tool, 'input_parameters') and tool.input_parameters:
                    md_content.append(f"  - Parameters: `{tool.input_parameters}`\n")
            md_content.append("\n")
        
        # Context
        if hasattr(test_case, 'retrieval_context') and test_case.retrieval_context:
            md_content.append("## 📚 Retrieval Context\n\n")
            for i, ctx in enumerate(test_case.retrieval_context, 1):
                md_content.append(f"{i}. {ctx[:200]}{'...' if len(ctx) > 200 else ''}\n")
            md_content.append("\n")
        
        if hasattr(test_case, 'context') and test_case.context:
            md_content.append("## 📄 Context (Ground Truth)\n\n")
            for i, ctx in enumerate(test_case.context, 1):
                md_content.append(f"{i}. {ctx[:200]}{'...' if len(ctx) > 200 else ''}\n")
            md_content.append("\n")
        
        # Metrics Results
        md_content.append("## 📊 Evaluation Metrics\n\n")
        md_content.append("| Metric | Score | Threshold | Status | Result |\n")
        md_content.append("|--------|-------|-----------|--------|--------|\n")
        
        # Access metrics from test case's metrics_data if available
        for metric in metrics:
            metric_name = metric.__class__.__name__.replace("Metric", "")
            threshold = getattr(metric, 'threshold', None)
            
            # Try to get score from test case's metrics_data
            score = None
            is_successful = None
            
            if hasattr(test_case, 'metrics_data') and test_case.metrics_data:
                for metric_data in test_case.metrics_data:
                    if metric_data.__class__.__name__ == metric.__class__.__name__:
                        score = getattr(metric_data, 'score', None)
                        try:
                            is_successful = metric_data.is_successful()
                        except Exception:
                            is_successful = None
                        break
            
            # Determine pass/fail
            if is_successful is None:
                status = "❓"
                result = "Not measured"
            elif is_successful:
                status = "✅"
                result = "PASS"
            else:
                status = "❌"
                result = "FAIL"
            
            # Format score and threshold
            score_str = f"{score:.3f}" if score is not None else "N/A"
            threshold_str = f"{threshold:.2f}" if threshold is not None else "N/A"
            
            md_content.append(f"| {metric_name} | {score_str} | {threshold_str} | {status} | **{result}** |\n")
        
        md_content.append("\n")
        
        # Detailed Reasons
        md_content.append("## 💭 Detailed Evaluation Reasons\n\n")
        
        # Access reasons from test case's metrics_data if available
        if hasattr(test_case, 'metrics_data') and test_case.metrics_data:
            for metric_data in test_case.metrics_data:
                metric_name = metric_data.__class__.__name__.replace("Metric", "")
                reason = getattr(metric_data, 'reason', None)
                
                if reason:
                    md_content.append(f"### {metric_name}\n\n")
                    md_content.append(f"{reason}\n\n")
        else:
            md_content.append("*Evaluation reasons not available. Check console output for details.*\n\n")
        
        # Save to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("".join(md_content))
        
        print(f"  ✓ Saved: {filename}")
    
    # Save summary file as Markdown
    summary_file = results_path / "README.md"
    summary_content = []
    
    summary_content.append("# Evaluation Results Summary\n\n")
    summary_content.append(f"**Timestamp:** {timestamp}\n\n")
    summary_content.append(f"**Total Test Cases:** {len(test_cases)}\n\n")
    summary_content.append("---\n\n")
    
    summary_content.append("## 📋 Metrics Used\n\n")
    summary_content.append("| # | Metric | Threshold | Direction |\n")
    summary_content.append("|---|--------|-----------|----------|\n")
    for i, metric in enumerate(metrics, 1):
        metric_name = metric.__class__.__name__.replace("Metric", "")
        threshold = getattr(metric, 'threshold', None)
        threshold_str = f"{threshold:.2f}" if threshold is not None else "N/A"
        
        # Determine direction based on metric name
        lower_is_better = any(keyword in metric_name.lower() 
                             for keyword in ['hallucination', 'bias', 'toxicity'])
        direction = "⬇️ Lower better" if lower_is_better else "⬆️ Higher better"
        
        summary_content.append(f"| {i} | {metric_name} | {threshold_str} | {direction} |\n")
    
    summary_content.append("\n## 🧪 Test Cases\n\n")
    for idx, tc in enumerate(test_cases, 1):
        safe_input = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' 
                           for c in tc.input[:50])
        filename = f"test_{idx:02d}_{safe_input}.md"
        summary_content.append(f"{idx}. [{tc.input}](./{filename})\n")
    
    summary_content.append("\n## 📈 Overall Results\n\n")
    summary_content.append("*Note: Individual metric pass/fail rates are available in each test case file.*\n\n")
    
    summary_content.append("---\n\n")
    summary_content.append("*Generated by DeepEval Quality Evaluation Framework*\n")
    
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.write("".join(summary_content))
    
    print("  ✓ Saved: README.md")
    print(f"\n✅ All results saved to: {results_path.absolute()}")


def main():
    """Run the evaluation."""
    # Create output directory with timestamp FIRST
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_path = Path("evaluation_results") / timestamp
    results_path.mkdir(parents=True, exist_ok=True)
    
    # Create consolidated output file
    output_file = results_path / "evaluation_output.txt"
    
    # Redirect all output to both console and file
    with open(output_file, 'w', encoding='utf-8') as f:
        # Create a tee-like output that writes to both stdout and file
        class TeeOutput:
            def __init__(self, *files):
                self.files = files
            def write(self, obj):
                for f in self.files:
                    f.write(obj)
                    f.flush()
            def flush(self):
                for f in self.files:
                    f.flush()
        
        tee = TeeOutput(sys.stdout, f)
        
        with redirect_stdout(tee), redirect_stderr(tee):
            print("="*80)
            print("DreamFarm Agent Quality Evaluation")
            print("="*80)
            print()
            print(f"📁 Output file: {output_file.absolute()}")
            print()
            
            # Setup
            print("Setting up evaluation...")
            evaluation_model = create_evaluation_model()
            metrics = create_metrics(evaluation_model)
            test_cases = create_sample_test_cases()
            
            print(f"[OK] Created {len(metrics)} metrics")
            print(f"[OK] Created {len(test_cases)} test cases")
            print()
            
            print("="*80)
            print("Running Evaluation...")
            print("="*80)
            print()
            
            # Evaluate and save each test case individually
            all_passed = 0
            all_failed = 0
            
            for idx, test_case in enumerate(test_cases, 1):
                print(f"\n{'='*80}")
                print(f"Test Case {idx}/{len(test_cases)}: {test_case.input[:60]}...")
                print(f"{'='*80}\n")
                
                # Evaluate single test case
                try:
                    evaluate(
                        test_cases=[test_case],
                        metrics=metrics,
                    )
                    
                    # Count passes/failures (DeepEval prints this but we track it)
                    all_passed += 1  # Simplified - could parse actual results
                    
                except Exception as e:
                    print(f"[ERROR] Test case evaluation failed: {e}")
                    all_failed += 1
                    continue
            
            # Create summary README
            summary_file = results_path / "README.md"
            summary_content = []
            
            summary_content.append("# Evaluation Results Summary\n\n")
            summary_content.append(f"**Timestamp:** {timestamp}\n\n")
            summary_content.append(f"**Total Test Cases:** {len(test_cases)}\n\n")
            summary_content.append("---\n\n")
            
            summary_content.append("## 📋 Metrics Used\n\n")
            summary_content.append("| # | Metric | Threshold | Direction |\n")
            summary_content.append("|---|--------|-----------|----------|\n")
            for i, metric in enumerate(metrics, 1):
                metric_name = metric.__class__.__name__.replace("Metric", "")
                threshold = getattr(metric, 'threshold', None)
                threshold_str = f"{threshold:.2f}" if threshold is not None else "N/A"
                
                lower_is_better = any(keyword in metric_name.lower() 
                                     for keyword in ['hallucination', 'bias', 'toxicity'])
                direction = "⬇️ Lower better" if lower_is_better else "⬆️ Higher better"
                
                summary_content.append(f"| {i} | {metric_name} | {threshold_str} | {direction} |\n")
            
            summary_content.append("\n## 🧪 Test Cases\n\n")
            for idx, tc in enumerate(test_cases, 1):
                summary_content.append(f"{idx}. **{tc.input}**\n")
                summary_content.append("   - See detailed results in evaluation_output.txt\n\n")
            
            summary_content.append("## 📝 Notes\n\n")
            summary_content.append("- All evaluation results are saved to `evaluation_output.txt`\n")
            summary_content.append("- Each test case evaluated individually with all 8 metrics\n")
            summary_content.append("- Check evaluation_output.txt for metric scores, reasons, and pass/fail status\n\n")
            
            summary_content.append("---\n\n")
            summary_content.append("*Generated by DeepEval Quality Evaluation Framework*\n")
            
            with open(summary_file, 'w', encoding='utf-8') as sf:
                sf.write("".join(summary_content))
            
            print()
            print("="*80)
            print("EVALUATION SUMMARY")
            print("="*80)
            print()
            
            print(f"[OK] Evaluated {len(test_cases)} test cases with {len(metrics)} metrics each")
            print(f"📁 Summary saved to: {results_path.absolute()}/README.md")
            print(f"📄 Full output saved to: {output_file.absolute()}")
            print()
            print("Test Cases:")
            for i, tc in enumerate(test_cases, 1):
                print(f"  {i}. {tc.input}")
            print()
            
            print("Metrics Used:")
            for metric in metrics:
                metric_name = metric.__class__.__name__
                threshold = getattr(metric, 'threshold', 'N/A')
                print(f"  - {metric_name} (threshold: {threshold})")
            print()
            
            print("Note: All metric scores, reasons, and detailed results")
            print("are saved in evaluation_output.txt")
            print()
            
            print("="*80)
            print("[OK] Evaluation Complete")
            print("="*80)


if __name__ == "__main__":
    main()
