# OpenTelemetry GenAI Semantic Conventions - Decision

## Summary

**Decision: Use standard OpenTelemetry instrumentation** (`opentelemetry-instrumentation-openai`) instead of OpenInference.

## Investigation Results

### OpenInference vs OpenTelemetry GenAI Conventions

**OpenInference:**
- Uses custom semantic conventions: `llm.token_count.total`, `llm.model_name`, `llm.input_messages`
- Designed for Arize Phoenix observability platform
- Not compatible with standard OpenTelemetry GenAI semantic conventions
- **No configuration option** to emit OTel standard attributes

**Standard OpenTelemetry:**
- Uses official semantic conventions: `gen_ai.usage.input_tokens`, `gen_ai.request.model`, `gen_ai.input.messages`
- Industry standard, widely supported
- Compatible with Grafana, Tempo, and all OTel-compliant tools
- Official spec: https://opentelemetry.io/docs/specs/semconv/gen-ai/openai/

### Responses API Support Status

Both instrumentations support OpenAI's Responses API for structured outputs:

| Instrumentation | Responses API Support | Semantic Conventions |
|----------------|----------------------|---------------------|
| `opentelemetry-instrumentation-openai` v0.47.3+ | ✅ Yes | ✅ OTel GenAI (standard) |
| `openinference-instrumentation-openai` v0.1.25+ | ✅ Yes | ❌ OpenInference (custom) |

## Decision Rationale

1. **Standards Compliance**: We need standard OTel GenAI semantic conventions for:
   - Grafana dashboard compatibility
   - Tempo trace analysis
   - Industry-standard tooling

2. **Vendor Neutrality**: OpenInference is tied to Arize Phoenix platform

3. **Ecosystem Compatibility**: Standard OTel conventions work with all observability tools

4. **Future-Proofing**: Official OTel GenAI conventions are evolving as industry standard

## Implementation

### Current Configuration

**Dependencies (`pyproject.toml`):**
```toml
"opentelemetry-instrumentation-openai>=0.47.3"
```

**Instrumentation (`src/main.py`):**
```python
from opentelemetry.instrumentation.openai import OpenAIInstrumentor
OpenAIInstrumentor().instrument()
```

### Expected Attributes

Standard OpenTelemetry GenAI semantic conventions for OpenAI:

**Span Attributes:**
- `gen_ai.operation.name`: "chat" | "embeddings" | "text_completion"
- `gen_ai.request.model`: "gpt-4o" | "gpt-4"
- `gen_ai.response.model`: Actual model used
- `gen_ai.usage.input_tokens`: Number of prompt tokens
- `gen_ai.usage.output_tokens`: Number of completion tokens
- `gen_ai.response.finish_reasons`: ["stop"] | ["length"]

**Metric Attributes:**
- `gen_ai.client.token.usage`: Token usage metric
- `gen_ai.client.operation.duration`: Operation duration

## Verification

After deployment, verify traces contain standard attributes:

```bash
# Check traces in Grafana/Tempo
kubectl logs -l app=dreamfarm-agent --tail=100 | grep "gen_ai"
```

Look for attributes like:
- `gen_ai.request.model`
- `gen_ai.usage.input_tokens`
- `gen_ai.usage.output_tokens`

## References

- [OpenTelemetry GenAI Semantic Conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/openai/)
- [OpenInference Specification](https://arize-ai.github.io/openinference/spec/semantic_conventions.html)
- [SigNoz LLM Observability Analysis](https://signoz.io/blog/llm-observability-opentelemetry/)
- [OpenTelemetry Instrumentation OpenAI](https://github.com/open-telemetry/opentelemetry-python-contrib/tree/main/instrumentation/opentelemetry-instrumentation-openai)
