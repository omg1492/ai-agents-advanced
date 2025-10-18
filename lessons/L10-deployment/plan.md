# L10: Observability with OpenTelemetry

## Implementation Checklist

### 1. OpenTelemetry Collector Deployment (Foundation)
- [x] Create Kubernetes deployment for OTel Collector (single replica)
- [x] Configure collector config map with OTLP receiver (port 4317), batch processor, console exporter initially
- [x] Expose collector service as ClusterIP on port 4317
- **Test**: `kubectl logs -f <otel-collector-pod>` → should show "Collector started" ✅
- **Test**: `kubectl exec -it <any-pod> -- curl http://otel-collector:4317` → connection should succeed ✅

### 2. Tempo Backend Deployment
- [x] Deploy Tempo single-container pod (ephemeral, no persistence)
- [x] Expose Tempo UI via Kubernetes service (LoadBalancer or port-forward for demo)
- [x] Configure OTLP receiver endpoint (port 4317)
- **Test**: Access Tempo UI (`kubectl port-forward svc/signoz 3301:8080`) → UI should load ✅
- **Test**: Check Tempo readiness endpoint ✅

### 3. Wire Collector → Tempo/Grafana (Replaced Tempo)
- [x] Deployed Grafana Tempo as distributed tracing backend
- [x] Update collector ConfigMap: add `otlp/tempo` exporter pointing to tempo-distributor:4317
- [x] Fixed Tempo replication_factor=1 for single-instance deployment
- [x] Fixed Grafana datasource URL to point to tempo-query-frontend:3200
- [x] **Test**: Send manual test span via job → ✅ trace visible in Grafana UI (span ID: e48578b317e1ca90dd67636048a9d646)
- [x] **Test**: Verified OTel Collector → Tempo pipeline working without errors ✅

### 4. DreamFarm Agent Instrumentation (First App)
- [x] Add OpenTelemetry dependencies to `agents/dreamfarm-agent/pyproject.toml`
- [x] Replace Traceloop SDK with direct OpenTelemetry instrumentation (root cause: Traceloop.init() not compatible with custom TracerProvider)
- [x] Initialize OpenTelemetry in `src/main.py` startup (TracerProvider, OTLP exporter)
- [x] Add direct OpenAI instrumentation: `OpenAIInstrumentor().instrument()`
- [x] Add PostgreSQL instrumentation: `opentelemetry-instrumentation-psycopg`
- [x] Add SQLAlchemy instrumentation: `opentelemetry-instrumentation-sqlalchemy`
- [x] Instrument FastAPI app with FastAPIInstrumentation
- [x] Enable full prompt/completion logging: `OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT=true`
- [x] Add environment variables to Kubernetes deployment: `OTEL_SERVICE_NAME=dreamfarm-agent`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`
- [x] **Test (Fast Iteration)**: Created minimal test pod with direct instrumentation → traces visible in Grafana ✅
- [ ] **Test (K8s)**: Build and deploy updated agent image → verify OpenAI + PostgreSQL spans in Grafana
- [ ] **Test (K8s)**: Make chat request → verify full trace with LLM prompts/completions in span logs

### 5. Business Dimension Injection (DreamFarm Agent)
- [x] Created OpenTelemetry middleware to extract user context from JWT
- [x] Set span attributes: `user_id`, `is_vip` (from auth), `agent_type=dreamfarm`, `experiment=production`
- [x] Extract `thread_id` from request path for thread-based endpoints
- [x] Add `OTEL_EXPERIMENT` environment variable to deployment
- [ ] **Test**: Make authenticated chat request → inspect trace in Grafana → verify custom attributes visible
- [ ] **Test**: Filter traces by `is_vip=true` in Grafana → should show only VIP user requests
- [ ] **Test**: Make unauthenticated request → verify `user_id=anonymous` attribute set

### 6. OpenAI Instrumentation Provider Selection (All Services)
- [x] **DreamFarm Agent**: Implemented dual instrumentation support (OpenInference + standard OTel)
- [ ] **Chef Agent**: Add same dual instrumentation pattern
- [ ] **MCP Servers**: Add same dual instrumentation pattern to all MCP servers

**Implementation Pattern**:
```python
# In pyproject.toml
dependencies = [
    "openinference-instrumentation-openai>=0.1.34",  # Works NOW with Responses API streaming
    "opentelemetry-instrumentation-openai>=0.47.3",  # Standard GenAI conventions (awaiting fix)
]

# In src/main.py (after OTel TracerProvider initialization)
otel_provider = os.getenv("OTEL_INSTRUMENTATION_PROVIDER", "opentelemetry").lower()

if otel_provider == "openinference":
    from openinference.instrumentation.openai import OpenAIInstrumentor
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    print("[OK] OpenAI instrumented with OpenInference (Responses API streaming supported)")
else:
    from opentelemetry.instrumentation.openai import OpenAIInstrumentor
    OpenAIInstrumentor().instrument(tracer_provider=provider)
    print("[OK] OpenAI instrumented with standard OpenTelemetry (awaiting Responses API streaming fix)")
```

```yaml
# In Kubernetes deployment (temporarily use OpenInference)
env:
  - name: OTEL_INSTRUMENTATION_PROVIDER
    value: "openinference"  # Use until PR #3396 is merged
```

**Rationale**:
- **OpenInference** supports Responses API streaming NOW but uses custom semantic conventions
- **Standard OTel** uses GenAI conventions (Langfuse-compatible) but doesn't support Responses API streaming yet ([PR #3396](https://github.com/traceloop/openllmetry/pull/3396))
- **Current**: Use OpenInference for immediate observability
- **Future**: Switch to standard OTel once PR #3396 is merged (better Langfuse compatibility)

**Test**: 
- Verify traces appear in Grafana with either provider
- OpenInference: Look for `llm.token_count.total` attribute
- Standard OTel: Look for `gen_ai.usage.total_tokens` attribute

**Documentation**: See `docs/ImplementationLog.md` and `docs/CommonErrors.md` for detailed explanation and troubleshooting

---

### 7. Chef Agent Instrumentation
- [ ] Add OpenTelemetry instrumentation to `agents/chef-agent/pyproject.toml` (both providers like DreamFarm)
- [ ] Initialize in Chef Agent startup with `agent_type=chef`
- [ ] Add `OTEL_INSTRUMENTATION_PROVIDER=openinference` to Chef Agent deployment
- [ ] Deploy updated Chef Agent
- **Test**: Trigger DreamFarm→Chef delegation → verify trace spans both agents in Tempo
- **Test**: Verify trace shows parent-child relationship (DreamFarm calls Chef)
- **Test**: Check `agent_type` attribute correctly distinguishes services

### 8. NGINX Ingress OpenTelemetry
- [ ] Enable OpenTelemetry in NGINX Ingress Helm values (`enable-opentelemetry: "true"`, set collector endpoint)
- [ ] Upgrade ingress: `helm upgrade ingress-nginx ...`
- **Test**: Make request via ingress → verify NGINX span appears as root in Tempo trace
- **Test**: Verify W3C Trace Context headers propagate (check application logs for `traceparent` header)
- **Test**: Confirm HTTP metrics (status code, latency) visible in NGINX spans

### 9. MCP Server Instrumentation (Optional)
- [ ] Add dual instrumentation to MCP servers (`mcp-chef-services`, `mcp-public-farmer-tools`, `mcp-visualization-generator`)
- [ ] Set `agent_type=mcp-<service-name>` for each
- [ ] Add `OTEL_INSTRUMENTATION_PROVIDER=openinference` to all MCP server deployments
- **Test**: Trigger tool call → verify MCP server spans appear in trace chain
- **Test**: Verify full trace: NGINX → DreamFarm Agent → MCP Server → OpenAI
- 
### 10. Langfuse Backend Deployment
- [ ] Deploy Langfuse single-container pod
- [ ] Expose Langfuse UI via service
- [ ] Update collector ConfigMap: add `otlp/langfuse` exporter, update pipeline to dual-export
- [ ] Restart collector
- **Test**: Access Langfuse UI (`kubectl port-forward svc/langfuse 3000:3000`)
- **Test**: Make chat request → verify same trace appears in BOTH Tempo and Langfuse
- **Test**: Check Langfuse shows LLM-specific views (token counts, prompts) that Tempo doesn't emphasize


### 11. End-to-End Validation & Demo Queries
- [ ] Generate diverse test traffic: VIP user, non-VIP user, multi-agent delegation, tool calls, errors
- **Test**: Tempo service map shows all components (NGINX, agents, MCP servers)
- **Test**: Filter by `is_vip=true` → verify only VIP traces
- **Test**: Filter by `experiment=production` → verify all traces tagged
- **Test**: Find slowest LLM calls in Langfuse → verify token cost tracking
- **Test**: Trigger intentional error → verify error spans flagged in both backends
- [ ] Document example queries and screenshots in `docs/ImplementationLog.md`

---

## Incremental Testing Strategy

**Order of Operations** (validated at each step):
1. **Collector alone** → verify it starts and accepts connections
2. **Collector + Tempo** → verify pipeline works with manual test span
3. **One app (DreamFarm)** → verify auto-instrumentation captures LLM calls
4. **Business dimensions** → verify custom attributes propagate
5. **Second app (Chef)** → verify multi-service traces
6. **Infrastructure (NGINX)** → verify full request path traced
7. **Second backend (Langfuse)** → verify dual-export works
8. **Optional services (MCP)** → verify complete tool call chains
9. **Production scenarios** → verify all query use cases work

**Rollback Points**: Each step can be reverted independently (environment variables, Helm rollback, ConfigMap changes).
