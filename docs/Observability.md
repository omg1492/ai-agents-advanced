# Observability Strategy

## Overview

This document describes our comprehensive observability strategy using OpenTelemetry for distributed tracing across all services in the DreamFarm AI application. Our approach focuses on standardization, flexibility, and deep visibility into AI agent behavior.

## Architecture

### High-Level Design

```
┌─────────────────────┐
│   AI Agents         │
│  - DreamFarm Agent  │
│  - Chef Agent       │
│  - MCP Servers      │
└──────────┬──────────┘
           │ OTLP/gRPC (port 4317)
           ▼
┌─────────────────────┐
│  OTel Collector     │
│  (Centralized)      │
└──────────┬──────────┘
           │
           ├─────────────────────┐
           ▼                     ▼
┌─────────────────────┐  ┌─────────────────────┐
│  Grafana Tempo      │  │  Langfuse (Future)  │
│  (Distributed       │  │  (LLM Analytics)    │
│   Tracing)          │  │                     │
└─────────────────────┘  └─────────────────────┘
```

**Key Design Principles**:

1. **Centralized Collection**: All services send traces to a single OpenTelemetry Collector
2. **Multiple Backends**: Collector routes traces to multiple backends (Tempo for general tracing, Langfuse for LLM-specific analysis)
3. **Auto-Instrumentation**: Automatic instrumentation for common frameworks (FastAPI, SQLAlchemy, PostgreSQL, OpenAI)
4. **Business Context**: Custom dimensions added via middleware (user_id, is_vip, agent_type, experiment)
5. **Standard Conventions**: Prefer OpenTelemetry GenAI semantic conventions for long-term compatibility

---

## Auto-Instrumentation Strategy

### Components Instrumented

We auto-instrument four critical components in every service:

#### 1. **FastAPI** (HTTP Server)
- **Library**: `opentelemetry-instrumentation-fastapi`
- **What it traces**: HTTP requests, response status codes, latency, headers
- **Span name format**: `GET /chat`, `POST /threads/{thread_id}/messages`
- **Key attributes**: `http.method`, `http.route`, `http.status_code`, `http.target`

#### 2. **SQLAlchemy** (ORM)
- **Library**: `opentelemetry-instrumentation-sqlalchemy`
- **What it traces**: Database queries, transactions, connection pooling
- **Span name format**: `SELECT`, `INSERT`, `UPDATE`
- **Key attributes**: `db.system=postgresql`, `db.statement` (SQL query)

#### 3. **Psycopg2** (PostgreSQL Driver)
- **Library**: `opentelemetry-instrumentation-psycopg2`
- **What it traces**: Low-level database operations, connection management
- **Span name format**: `postgresql.query`
- **Key attributes**: `db.name`, `db.user`, `db.connection_string`

#### 4. **OpenAI SDK** (LLM Calls)
- **Library**: Two options available (see next section)
- **What it traces**: LLM API calls, token usage, prompts/completions, tool calls
- **Span name format**: `openai.chat.completions`, `openai.responses.create`
- **Key attributes**: Model, tokens, messages (if enabled)

---

## OpenAI Instrumentation: Dual Provider Strategy

### Problem Statement

We use OpenAI's **Responses API with streaming** (`responses.create(stream=True)`), which is a newer API feature. This creates a compatibility challenge:

- **Standard OpenTelemetry**: Uses GenAI semantic conventions (ideal for Langfuse), but doesn't support Responses API streaming yet ([GitHub PR #3396](https://github.com/traceloop/openllmetry/pull/3396))
- **OpenInference**: Supports Responses API streaming NOW, but uses custom semantic conventions (may not be fully compatible with Langfuse)

### Solution: Environment-Based Switching

We implement **both** instrumentation providers and switch between them via environment variable:

```python
# In pyproject.toml - install both packages
dependencies = [
    # Standard OpenTelemetry (GenAI semantic conventions)
    "opentelemetry-instrumentation-openai>=0.47.3",
    
    # OpenInference (custom semantic conventions, streaming support)
    "openinference-instrumentation-openai>=0.1.34",
]

# In src/main.py - conditional instrumentation
otel_provider = os.getenv("OTEL_INSTRUMENTATION_PROVIDER", "opentelemetry").lower()

if otel_provider == "openinference":
    from openinference.instrumentation.openai import OpenAIInstrumentor
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    print("[OK] OpenAI instrumented with OpenInference")
else:
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    print("[OK] OpenAI instrumented with standard OpenTelemetry")
```

### Configuration

**Helm Chart (values.yaml)**:
```yaml
otel:
  # Default to standard OTel (future-compatible)
  instrumentationProvider: "opentelemetry"
```

**Terraform Override (kubernetes.demo.tf)**:
```terraform
# Temporarily use OpenInference for Responses API streaming
set {
  name  = "otel.instrumentationProvider"
  value = "openinference"  # Switch to "opentelemetry" once PR #3396 merges
}
```

**Local Development (.env)**:
```bash
# Use OpenInference for immediate streaming support
OTEL_INSTRUMENTATION_PROVIDER=openinference

# Or use standard OTel (default)
# OTEL_INSTRUMENTATION_PROVIDER=opentelemetry
```

### Semantic Convention Differences

| Attribute | Standard OTel (GenAI) | OpenInference |
|-----------|----------------------|---------------|
| **Input tokens** | `gen_ai.usage.input_tokens` | `llm.token_count.input` |
| **Output tokens** | `gen_ai.usage.output_tokens` | `llm.token_count.output` |
| **Total tokens** | `gen_ai.usage.total_tokens` | `llm.token_count.total` |
| **Model name** | `gen_ai.request.model` | `llm.model_name` |
| **Messages** | `gen_ai.input.messages` | `llm.input_messages` |
| **System prompt** | `gen_ai.system` | `llm.system` |

**Implications**:
- **Grafana Tempo**: Works with both (trace visualization doesn't depend on attribute names)
- **Langfuse**: Expects standard GenAI conventions for LLM-specific features (cost tracking, prompt management)
- **Custom Queries**: Must account for different attribute names when filtering/aggregating

### Migration Timeline

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Current (Oct 2025)                                 │
│ - Use OpenInference (OTEL_INSTRUMENTATION_PROVIDER=openinference) │
│ - Responses API streaming works NOW                         │
│ - Limited Langfuse compatibility                            │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: After PR #3396 Merges (Q1 2026 estimated)          │
│ - Switch to standard OTel (OTEL_INSTRUMENTATION_PROVIDER=opentelemetry) │
│ - Test Responses API streaming with standard instrumentation│
│ - Verify Langfuse integration works correctly                │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: Long-term (Q2 2026)                                │
│ - Remove OpenInference dependency from pyproject.toml       │
│ - Standardize on OpenTelemetry GenAI conventions             │
│ - Full Langfuse feature compatibility                        │
└─────────────────────────────────────────────────────────────┘
```

**Tracking**: Monitor [PR #3396](https://github.com/traceloop/openllmetry/pull/3396) for merge status.

---

## Implementation Details

### Initialization Order (Critical!)

OpenTelemetry auto-instrumentation **must** be initialized **before** importing instrumented libraries. Our implementation follows this strict order:

```python
# 1. Load environment variables FIRST
load_dotenv()

# 2. Initialize OpenTelemetry TracerProvider
from opentelemetry.sdk.trace import TracerProvider
provider = TracerProvider(resource=Resource({SERVICE_NAME: "dreamfarm-agent"}))
trace.set_tracer_provider(provider)

# 3. Add OTLP exporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4317", insecure=True)
provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# 4. Instrument libraries BEFORE importing them
# Order: OpenAI → PostgreSQL → SQLAlchemy
OpenAIInstrumentor().instrument(tracer_provider=provider)
Psycopg2Instrumentor().instrument()
SQLAlchemyInstrumentor().instrument()

# 5. NOW import FastAPI and services (auto-instrumentation active)
from fastapi import FastAPI
from src.services.openai_service import OpenAIService
```

**Why This Order Matters**:
- Instrumentors patch library code at import time
- If you import before instrumenting, patching won't work
- Result: Missing spans, incomplete traces

### FastAPI Instrumentation

FastAPI is instrumented automatically after initialization:

```python
# After app creation
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

app = FastAPI(title="DreamFarm Agent")

# Instrument FastAPI app (if OTel enabled)
if otel_enabled:
    FastAPIInstrumentor.instrument_app(app)
    print("[OK] FastAPI instrumented for HTTP tracing")
```

This creates spans for:
- All HTTP requests (GET, POST, etc.)
- Request/response headers
- Status codes
- Latency measurements

---

## Custom Business Dimensions

We enrich traces with business context using FastAPI middleware. This allows filtering traces by user type, experiment, or agent in observability tools.

### Middleware Implementation

```python
@app.middleware("http")
async def add_business_dimensions(request: Request, call_next):
    """Add business context attributes to OpenTelemetry spans."""
    if otel_enabled:
        from opentelemetry import trace as otel_trace
        
        span = otel_trace.get_current_span()
        if span and span.is_recording():
            # 1. Static agent identifier
            span.set_attribute("agent_type", "dreamfarm")
            
            # 2. Experiment/environment tag
            experiment = os.getenv("OTEL_EXPERIMENT", "production")
            span.set_attribute("experiment", experiment)
            
            # 3. User context from JWT
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer ") and auth_service is not None:
                try:
                    token = auth_header.split(" ", 1)[1].strip()
                    claims = auth_service.validate(token)
                    username, is_vip = auth_service.extract_identity(claims)
                    
                    span.set_attribute("user_id", username)
                    span.set_attribute("is_vip", is_vip)
                except Exception:
                    span.set_attribute("user_id", "anonymous")
                    span.set_attribute("is_vip", False)
            else:
                span.set_attribute("user_id", "anonymous")
                span.set_attribute("is_vip", False)
            
            # 4. Thread context from URL path
            path = request.url.path
            if "/threads/" in path:
                parts = path.split("/")
                if len(parts) > 2 and parts[1] == "threads":
                    thread_id = parts[2]
                    if thread_id:
                        span.set_attribute("thread_id", thread_id)
    
    response = await call_next(request)
    return response
```

### Custom Dimensions Explained

| Dimension | Source | Purpose | Example Values |
|-----------|--------|---------|----------------|
| **agent_type** | Static config | Identify which service created the span | `dreamfarm`, `chef`, `mcp-visualization` |
| **experiment** | `OTEL_EXPERIMENT` env var | A/B testing, staging vs prod | `production`, `staging`, `experiment-a` |
| **user_id** | JWT `preferred_username` claim | User-level filtering and analysis | `john.doe`, `anonymous` |
| **is_vip** | JWT `groups` or `is_vip` claim | VIP vs regular user segmentation | `true`, `false` |
| **thread_id** | URL path parsing | Conversation-level tracing | `550e8400-e29b-41d4-a716-446655440000` |

### Use Cases

**1. Filter VIP User Requests**:
```
# In Grafana Tempo
is_vip = true
```

**2. Compare Experiments**:
```
# Compare latency between experiments
experiment = experiment-a vs experiment = production
```

**3. Track Conversation Threads**:
```
# All spans for a specific conversation
thread_id = 550e8400-e29b-41d4-a716-446655440000
```

**4. Service-Level Metrics**:
```
# DreamFarm agent specific performance
agent_type = dreamfarm
```

---

## Configuration

### Environment Variables

All services use these standard OpenTelemetry environment variables:

```bash
# === Core OpenTelemetry Configuration ===
OTEL_SERVICE_NAME=dreamfarm-agent              # Service identifier
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317  # Collector endpoint
OTEL_EXPORTER_OTLP_PROTOCOL=grpc               # Protocol (gRPC recommended)
OTEL_TRACES_EXPORTER=otlp                      # Exporter type

# === OpenAI Instrumentation Provider ===
# Options: "opentelemetry" (standard, future Langfuse) or "openinference" (streaming NOW)
OTEL_INSTRUMENTATION_PROVIDER=openinference    # Use until PR #3396 merges

# === Message Content Logging ===
# WARNING: May log sensitive data (prompts, completions)
OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true

# === Business Dimensions ===
OTEL_EXPERIMENT=production                     # Custom experiment tag
```

### Kubernetes Deployment

**Deployment YAML** (excerpt from `deployment-dreamfarm-agent.yaml`):
```yaml
env:
  # OpenTelemetry Configuration
  - name: OTEL_SERVICE_NAME
    value: "dreamfarm-agent"
  - name: OTEL_EXPORTER_OTLP_ENDPOINT
    value: "http://otel-collector:4317"
  - name: OTEL_EXPORTER_OTLP_PROTOCOL
    value: "grpc"
  - name: OTEL_TRACES_EXPORTER
    value: "otlp"
  - name: OTEL_EXPERIMENT
    value: "production"
  - name: OTEL_INSTRUMENTATION_PROVIDER
    value: {{ .Values.otel.instrumentationProvider | quote }}
  - name: OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT
    value: "true"
```

### Helm Chart Values

**values.yaml**:
```yaml
otel:
  # Default to standard OpenTelemetry (future-compatible)
  instrumentationProvider: "opentelemetry"
```

**Terraform Override** (for immediate streaming support):
```terraform
set {
  name  = "otel.instrumentationProvider"
  value = "openinference"
}
```

---

## OpenTelemetry Collector Configuration

The collector receives traces from all services and routes them to backends.

### Collector ConfigMap

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317  # All services send here
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:
    timeout: 10s
    send_batch_size: 1024

exporters:
  otlp/tempo:
    endpoint: tempo-distributor:4317
    tls:
      insecure: true
  
  # Future: Langfuse exporter
  # otlp/langfuse:
  #   endpoint: langfuse:4317

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo]
```

### Service Definition

```yaml
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
spec:
  type: ClusterIP
  ports:
    - name: otlp-grpc
      port: 4317
      targetPort: 4317
    - name: otlp-http
      port: 4318
      targetPort: 4318
  selector:
    app: otel-collector
```

---

## Observability Backends

### Grafana Tempo (Distributed Tracing)

**Purpose**: General-purpose distributed tracing for all services

**Features**:
- Trace visualization with service maps
- Span-level details (duration, attributes, events)
- Search by trace ID, service name, custom attributes
- Trace comparison (slow vs fast requests)

**Access**: Port-forward or ingress
```bash
kubectl port-forward svc/tempo-query-frontend 3200:3200
```

**Query Examples**:
```
# Find all traces for VIP users
{ is_vip = true }

# Find slow LLM calls (>10s)
{ name = "openai.chat.completions" } && { duration > 10s }

# Find all traces for a conversation
{ thread_id = "550e8400-..." }
```

### Langfuse (Future - LLM Analytics)

**Purpose**: LLM-specific observability and analytics

**Features**:
- Prompt management and versioning
- Token cost tracking
- Model performance comparison
- User feedback correlation
- Prompt engineering insights

**Requirements**:
- Standard OpenTelemetry GenAI semantic conventions
- Will work once we switch to `OTEL_INSTRUMENTATION_PROVIDER=opentelemetry`

**Deployment** (planned):
```yaml
exporters:
  otlp/langfuse:
    endpoint: langfuse:4317
    tls:
      insecure: true

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo, otlp/langfuse]  # Dual export
```

---

## Testing Strategy

### Verify Instrumentation Works

**1. Check Service Logs**:
```bash
kubectl logs -l app=dreamfarm-agent | grep -i "instrumented\|otel"
```

Expected output:
```
[OK] OpenAI instrumented with OpenInference (Responses API streaming supported)
[OK] PostgreSQL (psycopg2) instrumented for database tracing
[OK] SQLAlchemy instrumented for ORM tracing
[OK] FastAPI instrumented for HTTP tracing
[OK] OpenTelemetry initialized: service=dreamfarm-agent endpoint=http://otel-collector:4317
```

**2. Check Collector Logs**:
```bash
kubectl logs -l app=otel-collector | grep -i "export\|tempo"
```

Expected output:
```
Traces exported: 42 spans
OTLP exporter: tempo-distributor:4317
```

**3. Verify Traces in Grafana**:
```bash
kubectl port-forward svc/tempo-query-frontend 3200:3200
```
Open Grafana → Explore → Tempo → Search for recent traces

**4. Test Custom Dimensions**:
Make authenticated request:
```bash
curl -H "Authorization: Bearer $TOKEN" https://dreamfarm-agent.domain/chat
```

In Grafana, verify span has:
- `user_id` = username from JWT
- `is_vip` = true/false based on user
- `agent_type` = "dreamfarm"
- `experiment` = "production"

---

## Troubleshooting

### No Traces Appearing

**Symptoms**: No spans visible in Grafana Tempo

**Diagnosis**:
```bash
# 1. Check if service initialized OTel
kubectl logs -l app=dreamfarm-agent | grep "OpenTelemetry initialized"

# 2. Check collector is receiving spans
kubectl logs -l app=otel-collector | grep "Traces received"

# 3. Check Tempo is accessible
kubectl exec -it <otel-collector-pod> -- curl http://tempo-distributor:4317
```

**Solutions**:
- Verify `OTEL_EXPORTER_OTLP_ENDPOINT` points to correct collector
- Ensure collector service is running: `kubectl get svc otel-collector`
- Check network policies allow traffic between pods
- Verify TracerProvider initialization happens before library imports

### Health Check Spans Cluttering Traces

**Symptoms**: Too many spans for `/health` endpoint in Grafana

**Solution**: Health checks are excluded from tracing using FastAPI instrumentation configuration:
```python
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

FastAPIInstrumentor.instrument_app(
    app,
    excluded_urls="/health"  # Don't create spans for health checks
)
```

**Rationale**: Health checks run frequently (every 5-10 seconds) and don't provide business value in traces. Excluding them reduces noise and collector load.

### Streaming Chunks Creating Too Many Spans

**Symptoms**: Each LLM streaming chunk creates a separate span, overwhelming traces

**Best Practice**: The instrumentation libraries (both OpenInference and standard OTel) handle streaming internally:
- **Single span per streaming request**: The entire stream is captured in one span
- **Chunk data as span events**: Individual chunks are logged as events within the span (not separate spans)
- **Token counts aggregated**: Total tokens counted across all chunks

**What You See**:
- ✅ One span for `openai.chat.completions.create` (streaming)
- ✅ Span duration covers entire stream time
- ✅ Token counts reflect full response
- ❌ NOT: Separate spans for each chunk

**Verification**:
```bash
# Check span count for a streaming request - should be reasonable
kubectl logs -l app=otel-collector | grep "SpansExported" | tail -5
```

If you see excessive spans (hundreds for a single request), this indicates a configuration issue. The instrumentation should aggregate chunks automatically.

### Missing Custom Dimensions on Child Spans

**Symptoms**: `user_id`, `is_vip`, `agent_type` appear on FastAPI span but not on database or OpenAI child spans

**Root Cause**: Custom dimensions not propagated via OpenTelemetry context

**Solution**: We use a custom `SpanProcessor` to propagate context attributes to all child spans:

```python
class ContextAttributeSpanProcessor(SpanProcessor):
    """Propagates context values to span attributes for all instrumentation layers."""
    
    def on_start(self, span, parent_context=None):
        """Called when span starts - add context attributes."""
        ctx = parent_context or otel_context.get_current()
        
        # Propagate custom dimensions from context to span
        user_id = otel_context.get_value("user_id", ctx)
        if user_id:
            span.set_attribute("user_id", user_id)
        
        is_vip = otel_context.get_value("is_vip", ctx)
        if is_vip is not None:
            span.set_attribute("is_vip", is_vip)
        
        # ... agent_type, experiment, thread_id
```

**Middleware sets context**:
```python
# In middleware, after extracting user from JWT
ctx = otel_context.get_current()
ctx = otel_context.set_value("user_id", user_id, ctx)
ctx = otel_context.set_value("is_vip", is_vip, ctx)

# Attach context for request duration
token = otel_context.attach(ctx)
try:
    response = await call_next(request)
finally:
    otel_context.detach(token)
```

**Verification**:
```bash
# Make authenticated request
curl -H "Authorization: Bearer $TOKEN" https://dreamfarm-agent.domain/chat

# In Grafana, verify ALL spans have custom attributes:
# - FastAPI span: ✅ user_id, is_vip, agent_type, experiment
# - PostgreSQL span: ✅ user_id, is_vip, agent_type, experiment  
# - OpenAI span: ✅ user_id, is_vip, agent_type, experiment
```

### Wrong Semantic Conventions

**Symptoms**: Langfuse not showing LLM data correctly, or attributes missing expected names

**Diagnosis**:
```bash
# Check which provider is active
kubectl logs -l app=dreamfarm-agent | grep "instrumented with"
```

Expected:
- OpenInference: `instrumented with OpenInference`
- Standard OTel: `instrumented with standard OpenTelemetry`

**Solution**:
```bash
# Switch provider via Helm values
helm upgrade demo ./charts/demo --set otel.instrumentationProvider=opentelemetry
```

### Missing Custom Dimensions

**Symptoms**: `user_id`, `is_vip`, or other custom attributes not in spans

**Diagnosis**:
```bash
# Check if middleware is running
kubectl logs -l app=dreamfarm-agent | grep -A5 "add_business_dimensions"

# Verify span is recording
# (Check application code logs)
```

**Solution**:
- Ensure middleware is registered: `@app.middleware("http")`
- Verify span is recording: `if span and span.is_recording()`
- Check JWT parsing: Auth service must extract claims correctly

### Responses API Streaming Not Traced

**Symptoms**: Non-streaming calls traced, but streaming calls missing spans

**Root Cause**: Standard OTel doesn't support Responses API streaming yet

**Solution**:
```bash
# Switch to OpenInference
helm upgrade demo ./charts/demo --set otel.instrumentationProvider=openinference
kubectl rollout restart deployment/dreamfarm-agent
```

---

## Best Practices

### 1. **Initialize Early**
- Load `.env` first
- Initialize OTel before importing any instrumented libraries
- Use `@asynccontextmanager` for FastAPI lifespan to ensure proper cleanup

### 2. **Minimize Sensitive Data Exposure**
- Set `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=false` in production
- Review span attributes before enabling full message logging
- Use span processors to filter sensitive data if needed

### 3. **Use Consistent Service Names**
- Match service name to deployment: `dreamfarm-agent`, `chef-agent`, `mcp-visualization`
- Avoid spaces or special characters
- Use lowercase with hyphens

### 4. **Add Business Context**
- Always set `agent_type` to identify service
- Use `experiment` for A/B testing or environment tagging
- Extract user context when available (not all requests have auth)

### 5. **Monitor Collector Health**
- Watch for export errors in collector logs
- Set up alerts for collector downtime
- Use batch processor to reduce network overhead

### 6. **Plan for Multiple Backends**
- Design collector config to support multiple exporters
- Test dual export (Tempo + Langfuse) before production
- Document backend-specific requirements (e.g., Langfuse needs GenAI conventions)

---

## Future Enhancements

### Short-term (Q1 2026)
- [ ] Switch to standard OTel once PR #3396 merges
- [ ] Deploy Langfuse backend
- [ ] Configure dual export (Tempo + Langfuse)
- [ ] Test Langfuse integration with standard conventions

### Medium-term (Q2 2026)
- [ ] Add metrics collection (Prometheus)
- [ ] Implement log correlation with trace IDs
- [ ] Add custom span events for key business logic
- [ ] Create Grafana dashboards for common queries

### Long-term (Q3 2026+)
- [ ] Implement sampling strategies for high-volume production
- [ ] Add tail-based sampling (keep all error traces, sample successful ones)
- [ ] Set up distributed trace aggregation across regions
- [ ] Integrate with incident management (PagerDuty, Opsgenie)

---

## References

- **OpenTelemetry Documentation**: https://opentelemetry.io/docs/
- **GenAI Semantic Conventions**: https://opentelemetry.io/docs/specs/semconv/gen-ai/
- **OpenInference Documentation**: https://github.com/Arize-ai/openinference
- **Grafana Tempo**: https://grafana.com/docs/tempo/latest/
- **Langfuse**: https://langfuse.com/docs
- **GitHub PR #3396** (Responses API streaming fix): https://github.com/traceloop/openllmetry/pull/3396

---

## Related Documentation

- [ImplementationLog.md](./ImplementationLog.md) - Implementation decisions and history
- [CommonErrors.md](./CommonErrors.md) - Troubleshooting guide with known issues
- [Design.md](./Design.md) - Overall system architecture
- [L10-deployment/plan.md](../lessons/L10-deployment/plan.md) - Observability deployment checklist
