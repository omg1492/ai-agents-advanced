># DreamFarm Agent Evaluation with DeepEval

This directory contains quality evaluation infrastructure for the DreamFarm Agent using [DeepEval](https://deepeval.com/), an open-source LLM evaluation framework.

## Overview

We evaluate the agent using **8 comprehensive metrics** covering RAG quality, safety, and business requirements:

### Core RAG Metrics (Pre-defined)
1. **Answer Relevancy** - Ensures responses are relevant to user queries
2. **Faithfulness** - Checks that responses don't hallucinate or contradict retrieved context

### Retrieval Quality Metrics (Pre-defined)
3. **Contextual Relevancy** - Evaluates if retrieved context is relevant to the query
4. **Contextual Precision** - Measures if relevant nodes are ranked higher in retrieval results

### Safety Metrics (Pre-defined)
5. **Hallucination** - Detects if output contradicts provided context
6. **Bias** - Identifies gender, racial, or political bias in responses
7. **Toxicity** - Flags toxic language or personal attacks

### Custom Business Metrics
8. **No Competitor Recommendation** (Brand Safety) - Ensures the agent never recommends competing marketplaces (Rohlík.cz, Košík.cz) or retail chains (Lidl, Billa, Albert, Tesco)

## Architecture

- **`custom_llm.py`** - Azure OpenAI wrapper compatible with DeepEval's `DeepEvalBaseLLM` interface
- **`custom_metrics.py`** - Custom G-Eval metrics for DreamFarm-specific requirements
- **`run_evaluation.py`** - Standalone evaluation script (recommended)
- **`test_agent_evaluation.py`** - Pytest-based evaluation test suite (alternative)

## Setup

### 1. Install Dependencies

```powershell
cd agents/dreamfarm-agent
uv sync
```

This installs `deepeval>=1.4.0` along with all other dependencies.

### 2. Configuration

Evaluation uses the same Azure OpenAI configuration as the agent (from `.env`):

```properties
OPENAI_API_KEY=<your-azure-openai-key>
OPENAI_BASE_URL=https://<your-resource>.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview
OPENAI_MODEL=gpt-5
```

The evaluation model (LLM-as-judge) is the **same GPT-5 model** used by the agent. This ensures:
- No additional API keys or services needed
- Consistent evaluation criteria
- Same cost model

## Running Evaluations

### Standalone Script (Recommended)

```powershell
cd tests/evaluation
uv run python run_evaluation.py
```

This runs all 8 metrics on 6 test cases and:
- Displays detailed results in console with full metric scores, reasons, and pass/fail status
- Saves a summary README to `evaluation_results/<timestamp>/README.md`
- Evaluates each test case individually so you can see progress

**Console Output:**
DeepEval prints comprehensive evaluation details for each test case including:
- Metric scores (0.0-1.0)
- Pass/Fail status based on thresholds
- Detailed reasoning for each metric score
- Overall pass rates per metric

**To save output to file** (recommended on Windows to avoid encoding issues):
```powershell
cd tests/evaluation
$env:PYTHONIOENCODING="utf-8"
uv run python run_evaluation.py 2>&1 | Tee-Object -FilePath "evaluation_results\run_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"
```

**Output Structure:**
```
evaluation_results/
└── 20250412_143022/
    └── README.md              # Summary with test case list and metrics
```

Console output contains all the detailed evaluation data that DeepEval generates.

### Pytest (Alternative)

```powershell
uv run pytest tests/evaluation/test_agent_evaluation.py::test_agent_evaluation_quick -v -s
```

## Evaluation Metrics Details

### 1. Answer Relevancy Metric
- **Threshold**: 0.7 (70% minimum)
- **Type**: Referenceless, LLM-as-judge
- **Purpose**: Ensures agent responses directly address user questions
- **Evaluation**: Extracts statements from output and checks relevance to input

### 2. Faithfulness Metric
- **Threshold**: 0.8 (80% minimum)
- **Type**: Reference-based, LLM-as-judge
- **Purpose**: Prevents hallucination - responses must align with retrieved context
- **Evaluation**: Compares claims in output against facts in `retrieval_context`

### 3. Contextual Relevancy Metric
- **Threshold**: 0.7 (70% minimum)
- **Type**: Reference-based, LLM-as-judge
- **Purpose**: Measures quality of retrieval - is the context relevant to the query?
- **Evaluation**: Extracts statements from `retrieval_context` and checks relevance to `input`

### 4. Contextual Precision Metric
- **Threshold**: 0.7 (70% minimum)
- **Type**: Reference-based, LLM-as-judge
- **Purpose**: Evaluates re-ranking - are relevant nodes ranked higher?
- **Evaluation**: Uses weighted cumulative precision emphasizing top results
- **Requires**: `expected_output` for ground truth

### 5. Hallucination Metric
- **Threshold**: 0.5 (50% maximum - lower is better)
- **Type**: Reference-based, LLM-as-judge
- **Purpose**: Detects contradictions between output and context
- **Evaluation**: Checks if `actual_output` contradicts `context`
- **Note**: Different from Faithfulness - uses `context` as source of truth

### 6. Bias Metric
- **Threshold**: 0.3 (30% maximum - lower is better)
- **Type**: Referenceless, LLM-as-judge
- **Purpose**: Detects gender, racial, political, or geographical bias
- **Evaluation**: Extracts opinions and classifies as biased/unbiased
- **Categories**: Gender, political, racial/ethnic, geographical bias

### 7. Toxicity Metric
- **Threshold**: 0.3 (30% maximum - lower is better)
- **Type**: Referenceless, LLM-as-judge
- **Purpose**: Identifies toxic language, personal attacks, mockery, hate speech
- **Evaluation**: Extracts opinions and classifies as toxic/non-toxic
- **Categories**: Personal attacks, mockery, hate, dismissive statements, threats

### 8. No Competitor Recommendation (Custom G-Eval)
- **Threshold**: 0.9 (90% minimum - strict)
- **Type**: Referenceless, LLM-as-judge (G-Eval)
- **Purpose**: Brand protection - prevent customer deflection to competitors
- **Checks**:
  - No recommendations for Rohlík.cz, Košík.cz, or other online marketplaces
  - No suggestions to shop at Lidl, Billa, Albert, Tesco, or other retail chains
  - No unfavorable comparisons of DreamFarm vs. competitors
- **Evaluation**: Multi-step LLM judging process:
  1. Detect competitor mentions
  2. Classify context (neutral fact vs. recommendation)
  3. Score based on brand safety (HIGH 0.9-1.0 for safe, LOW 0.0-0.3 for violations)

## Metrics Quick Reference

| # | Metric | Type | Threshold | Direction | Purpose |
|---|--------|------|-----------|-----------|---------|
| 1 | Answer Relevancy | Referenceless | 0.7 | Higher better | Response addresses question |
| 2 | Faithfulness | Reference-based | 0.8 | Higher better | No hallucination vs context |
| 3 | Contextual Relevancy | Reference-based | 0.7 | Higher better | Retrieved context is relevant |
| 4 | Contextual Precision | Reference-based | 0.7 | Higher better | Relevant nodes ranked higher |
| 5 | Hallucination | Reference-based | 0.5 | Lower better | No contradictions to context |
| 6 | Bias | Referenceless | 0.3 | Lower better | No gender/racial/political bias |
| 7 | Toxicity | Referenceless | 0.3 | Lower better | No toxic language |
| 8 | No Competitor Rec. | Referenceless | 0.9 | Higher better | No competitor mentions (custom) |

### Metric Categories

**Core RAG Metrics (1-2)**: Fundamental quality of RAG system's answers
- Answer Relevancy: Does the agent answer the user's actual question?
- Faithfulness: Does the agent hallucinate or contradict retrieved facts?

**Retrieval Quality Metrics (3-4)**: Evaluate whether retrieval fetches the right documents
- Contextual Relevancy: Is the retrieved context actually useful?
- Contextual Precision: Are the most relevant documents ranked first?

**Safety Metrics (5-7)**: Protect against harmful or problematic outputs
- Hallucination: Does output contradict the provided context?
- Bias: Does the agent exhibit bias in opinions?
- Toxicity: Does the agent use toxic language?

**Business Metrics (8)**: Custom metrics for DreamFarm-specific requirements
- No Competitor Recommendation: Ensures no competitor mentions or unfavorable comparisons

### Test Case Requirements

Different metrics require different fields in your `LLMTestCase`:

| Field | Required By | Purpose |
|-------|-------------|---------|
| `input` | ALL | User's question |
| `actual_output` | ALL | Agent's response |
| `expected_output` | Contextual Precision | Ground truth for ranking evaluation |
| `retrieval_context` | Faithfulness, Contextual Relevancy, Contextual Precision | Retrieved documents (list) |
| `context` | Hallucination | Source documents (list) |
| `tools_called` | (Future: Tool Correctness) | Tools used by agent |

**Tip**: Provide all fields for comprehensive evaluation.

## Understanding Results

### Console Output

Evaluation prints detailed results:

```
Test Case 1: Jaké bio rajčata máte skladem?...
  [✓ PASS] Answer Relevancy: 0.85
  [✓ PASS] Faithfulness: 0.92
  [✓ PASS] Tool Correctness: 0.88
  [✓ PASS] No Competitor Recommendation: 1.00
```

### Metric Interpretation

- **Score Range**: 0.0 - 1.0 (higher is better)
- **Pass/Fail**: Score >= threshold = PASS
- **Reason**: Each metric provides natural language explanation (when `include_reason=True`)

#### Score Meanings

**High-is-better metrics (1-4, 8):**
- 0.9-1.0: Excellent
- 0.7-0.9: Good
- 0.5-0.7: Needs improvement
- 0.0-0.5: Poor

**Low-is-better metrics (5-7):**
- 0.0-0.2: Excellent
- 0.2-0.4: Good
- 0.4-0.6: Needs improvement
- 0.6-1.0: Poor

### Common Failure Patterns

**Answer Relevancy Failures:**
- Agent goes off on tangent
- Answers different question than asked
- Provides generic fluff instead of specific answer

**Faithfulness Failures:**
- Agent invents product details not in context
- Agent makes up prices or stock levels
- Agent hallucinates producer information

**Contextual Relevancy Failures:**
- Vector search returned wrong products
- No relevant context retrieved at all
- Context is about different category/topic

**Contextual Precision Failures:**
- Best documents ranked low in list
- Irrelevant documents at top
- Re-ranker not working properly

**Hallucination Failures:**
- Output contradicts provided facts
- Different from Faithfulness: checks against `context` not `retrieval_context`

**Bias Failures:**
- "Women are better at X"
- "People from Y are all Z"
- Political statements disguised as facts

**Toxicity Failures:**
- "That's a stupid question"
- "You don't know what you're talking about"
- Sarcastic or mocking tone

**Competitor Recommendation Failures:**
- "You might find it cheaper at Lidl"
- "Rohlik.cz has better selection"
- Unfavorably comparing DreamFarm to competitors

### Results Files

After running `uv run python run_evaluation.py`, a summary is saved to:

```
evaluation_results/<timestamp>/
└── README.md                     # Summary: test cases and metrics overview
```

The README contains:
- List of all metrics used with thresholds
- List of all test cases evaluated
- Note: All detailed scores and reasons are in console output

**Best Practice:** Save console output to a file for later reference (see command above with `Tee-Object`).

### Best Practices

1. **Run regularly**: Evaluate after every agent change
2. **Track trends**: Compare timestamps to see improvement
3. **Focus on failures**: Fix lowest-scoring metrics first
4. **Read reasons**: DeepEval provides detailed explanations for scores
5. **Customize thresholds**: Adjust based on your quality requirements
6. **Add more test cases**: 6 is a start, aim for 20-50 production-like scenarios
7. **Monitor safety**: Bias and Toxicity should ALWAYS be low
8. **Protect brand**: No Competitor Recommendation should ALWAYS pass

## Extending Evaluations

### Adding Test Cases

Edit `sample_test_cases` fixture in `test_agent_evaluation.py`:

```python
LLMTestCase(
    input="Your test query",
    actual_output="Agent's response",
    expected_output="Ideal response",
    retrieval_context=["Context chunk 1", "Context chunk 2"],
    tools_called=[
        ToolCall(name="tool_name", arguments='{"param": "value"}')
    ]
)
```

### Adding Custom Metrics

Create new G-Eval metrics in `custom_metrics.py`:

```python
class YourCustomMetric(GEval):
    def __init__(self, threshold: float = 0.7, **kwargs):
        super().__init__(
            name="Your Metric Name",
            criteria="Clear description of what to evaluate",
            evaluation_steps=[
                "Step 1: Check for X",
                "Step 2: Verify Y",
                "Step 3: Score based on Z"
            ],
            evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
            threshold=threshold,
            **kwargs
        )
```

## Cost Considerations

- **Evaluation Model**: Uses the same Azure OpenAI GPT-5 as the agent
- **Per Test Case**: ~2-4 API calls per metric (varies by metric complexity)
- **Sample Test (4 cases × 4 metrics)**: ~16-64 API calls
- **Estimated Cost**: Similar to 16-64 agent chat turns

💡 **Tip**: Start with small sample evaluations during development. Run comprehensive evaluations on significant changes or pre-deployment.

## Integration with CI/CD

For continuous evaluation in CI pipelines:

1. **Create Golden Dataset**: Store test cases in JSON
2. **Add GitHub Workflow**: Run `deepeval test run` on PRs
3. **Set Thresholds**: Define acceptable metric scores
4. **Block Merges**: Fail builds if quality drops below thresholds

Example workflow:

```yaml
name: Agent Quality Evaluation
on: [pull_request]
jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
      - name: Install uv
        run: pip install uv
      - name: Run Evaluations
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
        run: |
          cd agents/dreamfarm-agent
          uv sync
          uv run pytest tests/evaluation/test_agent_evaluation.py -v
```

## Confident AI Integration (Optional)

DeepEval offers [Confident AI](https://app.confident-ai.com/) - a cloud platform for:
- Centralized test run history
- Visual dashboards and metrics tracking
- Regression testing across versions
- Team collaboration

**Note**: We're using pure open-source DeepEval without uploading data to external services. To enable Confident AI (optional):

```powershell
deepeval login
```

Then set `CONFIDENT_API_KEY` in your environment.

## Troubleshooting

### Import Errors

If you see `Import "deepeval" could not be resolved`:

```powershell
uv sync  # Re-sync dependencies
```

### Azure OpenAI Connection Issues

Verify environment variables:

```powershell
uv run python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_BASE_URL'))"
```

### Evaluation Timeouts

For large datasets, increase timeouts in metrics:

```python
metric = AnswerRelevancyMetric(model=evaluation_model, async_mode=True)
```

## References

- [DeepEval Documentation](https://deepeval.com/docs/getting-started)
- [G-Eval Metrics](https://deepeval.com/docs/metrics-llm-evals)
- [Agent Evaluation Guide](https://deepeval.com/docs/getting-started-agents)
- [Custom LLM Setup](https://deepeval.com/guides/guides-using-custom-llms)

## Support

For questions or issues with evaluations:
1. Check DeepEval documentation
2. Review `CommonErrors.md` in `docs/`
3. Ask in team channels
