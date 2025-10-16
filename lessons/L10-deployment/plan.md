# L10: Observability with OpenTelemetry

## Implementation Checklist

### 1. OpenTelemetry Collector Deployment (Foundation)
- [ ] Create Kubernetes deployment for OTel Collector (single replica)
- [ ] Configure collector config map with OTLP receiver (port 4317), batch processor, console exporter initially
- [ ] Expose collector service as ClusterIP on port 4317
- **Test**: `kubectl logs -f <otel-collector-pod>` → should show "Collector started"
- **Test**: `kubectl exec -it <any-pod> -- curl http://otel-collector:4317` → connection should succeed

### 2. SigNoz Backend Deployment
- [ ] Deploy SigNoz single-container pod (ephemeral, no persistence)
- [ ] Expose SigNoz UI via Kubernetes service (LoadBalancer or port-forward for demo)
- [ ] Configure OTLP receiver endpoint (port 4317)
- **Test**: Access SigNoz UI (`kubectl port-forward svc/signoz 3301:3301`) → UI should load
- **Test**: Check SigNoz readiness endpoint

### 3. Wire Collector → SigNoz
- [ ] Update collector ConfigMap: add `otlp/signoz` exporter, update pipeline
- [ ] Restart collector pod
- **Test**: `kubectl logs -f <otel-collector-pod>` → should show successful connection to SigNoz
- **Test**: Send manual test span via `curl` OTLP JSON to collector → verify appears in SigNoz UI

### 4. DreamFarm Agent Instrumentation (First App)
- [ ] Add OpenLLMetry dependencies to `agents/dreamfarm-agent/pyproject.toml`
- [ ] Initialize OpenLLMetry in `src/main.py` startup
- [ ] Add environment variables: `OTEL_SERVICE_NAME=dreamfarm-agent`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`
- **Test (Local)**: Run agent locally with `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317` (port-forward collector)
- **Test (Local)**: Make a chat request → check SigNoz for `dreamfarm-agent` service with LLM spans
- **Test (K8s)**: Deploy updated agent → verify traces in SigNoz with proper service name

### 5. Business Dimension Injection (DreamFarm Agent)
- [ ] Extract `user_id` and `is_vip` from JWT claims in auth middleware
- [ ] Set span attributes: `user_id`, `is_vip`, `thread_id`, `agent_type=dreamfarm`, `experiment=production`
- **Test**: Make authenticated chat request → inspect trace in SigNoz → verify custom attributes visible
- **Test**: Filter traces by `is_vip=true` in SigNoz → should show only VIP user requests
- **Test**: Make unauthenticated request → verify `user_id=anonymous` or similar default

### 6. Chef Agent Instrumentation
- [ ] Add OpenLLMetry to `agents/chef-agent/pyproject.toml`
- [ ] Initialize in Chef Agent startup with `agent_type=chef`
- [ ] Deploy updated Chef Agent
- **Test**: Trigger DreamFarm→Chef delegation → verify trace spans both agents in SigNoz
- **Test**: Verify trace shows parent-child relationship (DreamFarm calls Chef)
- **Test**: Check `agent_type` attribute correctly distinguishes services

### 7. NGINX Ingress OpenTelemetry
- [ ] Enable OpenTelemetry in NGINX Ingress Helm values (`enable-opentelemetry: "true"`, set collector endpoint)
- [ ] Upgrade ingress: `helm upgrade ingress-nginx ...`
- **Test**: Make request via ingress → verify NGINX span appears as root in SigNoz trace
- **Test**: Verify W3C Trace Context headers propagate (check application logs for `traceparent` header)
- **Test**: Confirm HTTP metrics (status code, latency) visible in NGINX spans

### 8. Langfuse Backend Deployment
- [ ] Deploy Langfuse single-container pod
- [ ] Expose Langfuse UI via service
- [ ] Update collector ConfigMap: add `otlp/langfuse` exporter, update pipeline to dual-export
- [ ] Restart collector
- **Test**: Access Langfuse UI (`kubectl port-forward svc/langfuse 3000:3000`)
- **Test**: Make chat request → verify same trace appears in BOTH SigNoz and Langfuse
- **Test**: Check Langfuse shows LLM-specific views (token counts, prompts) that SigNoz doesn't emphasize

### 9. MCP Server Instrumentation (Optional)
- [ ] Add OpenLLMetry to MCP servers (`mcp-chef-services`, `mcp-public-farmer-tools`, `mcp-visualization-generator`)
- [ ] Set `agent_type=mcp-<service-name>` for each
- **Test**: Trigger tool call → verify MCP server spans appear in trace chain
- **Test**: Verify full trace: NGINX → DreamFarm Agent → MCP Server → OpenAI

### 10. End-to-End Validation & Demo Queries
- [ ] Generate diverse test traffic: VIP user, non-VIP user, multi-agent delegation, tool calls, errors
- **Test**: SigNoz service map shows all components (NGINX, agents, MCP servers)
- **Test**: Filter by `is_vip=true` → verify only VIP traces
- **Test**: Filter by `experiment=production` → verify all traces tagged
- **Test**: Find slowest LLM calls in Langfuse → verify token cost tracking
- **Test**: Trigger intentional error → verify error spans flagged in both backends
- [ ] Document example queries and screenshots in `docs/ImplementationLog.md`

---

## Incremental Testing Strategy

**Order of Operations** (validated at each step):
1. **Collector alone** → verify it starts and accepts connections
2. **Collector + SigNoz** → verify pipeline works with manual test span
3. **One app (DreamFarm)** → verify auto-instrumentation captures LLM calls
4. **Business dimensions** → verify custom attributes propagate
5. **Second app (Chef)** → verify multi-service traces
6. **Infrastructure (NGINX)** → verify full request path traced
7. **Second backend (Langfuse)** → verify dual-export works
8. **Optional services (MCP)** → verify complete tool call chains
9. **Production scenarios** → verify all query use cases work

**Rollback Points**: Each step can be reverted independently (environment variables, Helm rollback, ConfigMap changes).
