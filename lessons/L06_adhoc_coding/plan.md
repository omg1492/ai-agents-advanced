# Lesson 06: Code Interpreter & Adhoc-Generated UI - Implementation Plan

## Overview

This lesson implements two major capabilities:
1. **Code Interpreter**: Execute Python code for data analysis and visualization using Azure OpenAI Responses API built-in tool
2. **Adhoc-Generated UI**: Create custom interactive HTML components through LLM-generated code, rendered securely in sandboxed iframes

**Primary Demo**: User uploads CSV file with weight tracking data → LLM analyzes trends, generates charts, creates custom dashboard cards.

---

## Prerequisites

- [ ] Responses API already integrated (from earlier lessons)
- [ ] File upload capability in frontend (or will implement)
- [ ] Azure OpenAI deployment supports code_interpreter tool
- [ ] React frontend with assistant-ui

---

## Phase 1: Code Interpreter Integration (Core Functionality)

### 1.1 Backend: Enable Code Interpreter Tool ✅ COMPLETED

- [x] **File**: `agents/dreamfarm-agent/src/services/config_service.py`
  - [x] Added `CodeInterpreterConfig` dataclass
  - [x] Added environment variable: `ENABLE_CODE_INTERPRETER=true`
  - [x] Added feature flag check

- [x] **File**: `agents/dreamfarm-agent/src/services/openai_service.py`
  - [x] Add `code_interpreter` to tools array in `get_tools()` method
  - [x] Tool registers when `config.code_interpreter.enabled=True`

- [x] **File**: `agents/dreamfarm-agent/.env.template` and `.env`
  - [x] Added `ENABLE_CODE_INTERPRETER` configuration
  - [x] Added `CODE_INTERPRETER_CONTAINER_TYPE` configuration

- [x] **Integration Tests**: `tests/test_code_interpreter_integration.py`
  - [x] Test tool registration
  - [x] Test mathematical calculations (PASSING)
  - [x] Test data analysis scenarios
  - [x] Test conversation continuity
  
**Note**: System prompt instructions for code interpreter are included in template and work automatically when tool is enabled.

### 1.2 Backend: File Upload to Responses API ✅ COMPLETED

- [x] **File**: `agents/dreamfarm-agent/src/models/file.py` (NEW)
  - [x] Created FileUploadResponse Pydantic model (file_id, filename, size_bytes, purpose, status)
  - [x] Created FileUploadError model for validation errors

- [x] **File**: `agents/dreamfarm-agent/src/main.py`
  - [x] Created endpoint `POST /files/upload`
  - [x] Accepts file upload (multipart/form-data)
  - [x] Validates file type: .csv, .xlsx, .xls, .json, .txt, .pdf, .png, .jpg, .jpeg, .gif
  - [x] Validates file size (max 30MB per Responses API limit)
  - [x] Validates empty files (rejects with 400)
  - [x] Checks code interpreter enabled (returns 503 if disabled)
  - [x] Uploads to Azure OpenAI Files API with purpose="assistants"
  - [x] Returns file_id, filename, size_bytes to frontend

- [x] **Integration Tests**: `tests/test_file_upload_integration.py` (NEW)
  - [x] Test CSV upload (PASSING - returns assistant-* file_id)
  - [x] Test Excel upload (PASSING)
  - [x] Test JSON upload (PASSING)
  - [x] Test TXT upload (PASSING)
  - [x] Test invalid file type rejection (PASSING)
  - [x] Test file too large rejection (PASSING)
  - [x] Test empty file rejection (PASSING)
  - [x] Feature disabled test (SKIPPED - TestClient limitation)

**Note**: Azure OpenAI file IDs use "assistant-" prefix (not "file-"). All validation tests pass (7 passed, 1 skipped).

### 1.3 Frontend: File Upload Component ✅ COMPLETED

- [x] **File**: `frontend/src/components/file-upload-button.tsx` (NEW)
  - [x] Created reusable file input component with upload icon
  - [x] Accepts types: `.csv,.xlsx,.xls,.json,.txt,.pdf,.png,.jpg,.jpeg,.gif`
  - [x] Shows upload progress with loading spinner
  - [x] Displays uploaded file name with remove button
  - [x] Handles errors (file too large >30MB, unsupported type, empty files)
  - [x] Validates file size and type before upload
  - [x] Triggers callback with file_id on success

- [x] **File**: `frontend/src/services/api.ts` (MODIFY)
  - [x] Added `uploadFile(file: File)` method using FormData
  - [x] Returns FileUploadResponse with file_id
  - [x] Updated `sendMessage` and `sendMessageStream` to accept optional attachments array
  - [x] Attachments passed as `string[]` of file_ids

- [x] **File**: `frontend/src/services/chatAdapter.ts` (MODIFY)
  - [x] Added `pendingAttachments: string[]` property
  - [x] Added `addAttachment(fileId: string)` method
  - [x] Added `clearAttachments()` method
  - [x] Passes attachments to `sendMessageStream` on message send
  - [x] Clears attachments after sending

- [x] **File**: `frontend/src/components/thread.tsx` (MODIFY)
  - [x] Imported FileUploadButton component
  - [x] Added FileUploadButton to Composer with VoiceButton and Send button in action bar
  - [x] Handles `onFileUploaded` callback to add attachment via chatAdapter
  - [x] Handles `onError` callback to display error message
  - [x] Error messages auto-clear after 5 seconds
  - [x] Fixed composer width to match suggestion buttons (w-full class)
  - [x] Improved button alignment (items-center for proper vertical alignment)

- [x] **File**: `agents/dreamfarm-agent/src/models/thread.py` (MODIFY)
  - [x] Added `attachments: list[str] = []` field to SendMessageRequest

- [x] **File**: `agents/dreamfarm-agent/src/services/openai_service.py` (MODIFY)
  - [x] Added `attachments: Optional[list[str]]` parameter to generate_response
  - [x] Converts file_ids to Responses API attachment format: `{"file_id": fid, "tools": [{"type": "code_interpreter"}]}`
  - [x] Passes attachments to `responses.create()` call

- [x] **File**: `agents/dreamfarm-agent/src/main.py` (MODIFY)
  - [x] Updated both `/threads/{thread_id}/messages` (non-streaming) endpoint
  - [x] Updated `/threads/{thread_id}/messages/stream` (streaming) endpoint
  - [x] Fixed streaming endpoint: attachments included in initial input message (not as stream parameter)
  - [x] Both endpoints properly format attachments for code_interpreter tool
  - [x] Added `from typing import Any` import for proper type hints

- [x] **File**: `tests/test_attachments_integration.py` (NEW)
  - [x] Created comprehensive integration tests for attachment functionality
  - [x] Test file upload + streaming message with attachment
  - [x] Test file upload + non-streaming message with attachment
  - [x] Test messages without attachments still work
  - [x] Test multiple attachments in single message

**Integration**: File upload button appears in chat input alongside Voice and Send buttons. User uploads file → receives file_id → file_id attached to next message → Responses API receives attachment formatted correctly for code_interpreter processing. Playwright MCP testing confirmed UI works end-to-end. Streaming bug fixed (attachments must be in input message, not stream kwargs).

**Next**: Proceed to Phase 1.4 (display code execution results).

### 1.4 Frontend: Display Code Interpreter Results

- [ ] **File**: `frontend/src/components/Messages/CodeInterpreterMessage.tsx` (NEW)
  - [ ] Component to display code execution results
  - [ ] Show executed Python code in syntax-highlighted block
  - [ ] Display logs output
  - [ ] Render generated images inline
  - [ ] Show downloadable files with links

- [ ] **File**: `frontend/src/components/Messages/MessageRenderer.tsx` (MODIFY)
  - [ ] Detect `code_interpreter_call` message type
  - [ ] Render using CodeInterpreterMessage component

- [ ] **Test**: Send message with file → verify chart renders, code shows, logs display

### 1.5 Demo Data & Testing

- [ ] **File**: `data/examples/weight_tracking.csv` (NEW)
  - [ ] Create sample CSV with columns: `date,weight_kg,notes`
  - [ ] 20-30 rows spanning 6 months
  - [ ] Include some weight variance for interesting charts

- [ ] **End-to-End Test**:
  - [ ] Upload `weight_tracking.csv`
  - [ ] Send message: "Analyze my weight data and show trends"
  - [ ] Verify agent calls code_interpreter
  - [ ] Verify chart generated and displayed
  - [ ] Verify statistics calculated correctly

---

## Phase 2: Adhoc-Generated UI (Custom Visualizations)

### 2.1 Backend: HTML Generator Service

- [ ] **File**: `agents/dreamfarm-agent/src/services/html_generator.py` (NEW)
  - [ ] Function `generate_html(description: str, data: dict, style: str) -> str`
  - [ ] Specialized system prompt for HTML generation:
  ```python
  HTML_GENERATOR_PROMPT = """
  You are an expert frontend developer. Generate self-contained HTML with inline CSS and JavaScript.
  
  REQUIREMENTS:
  - Use semantic HTML5 elements
  - All CSS must be inline in <style> tag
  - All JavaScript must be inline in <script> tag
  - No external resources (no CDN, no external URLs)
  - Use modern CSS (flexbox, grid, gradients, animations)
  - Make it visually appealing and responsive
  - Include appropriate ARIA labels for accessibility
  
  FORBIDDEN:
  - <script src="..."> or <link href="...">
  - eval(), Function(), innerHTML with user input
  - <iframe>, <object>, <embed> tags
  - javascript: protocol in attributes
  - External form actions
  
  RESPONSE FORMAT:
  Return only the HTML code, no explanations or markdown.
  """
  ```
  - [ ] Call GPT-4o with description + data
  - [ ] Return generated HTML string

- [ ] **File**: `agents/dreamfarm-agent/src/services/html_sanitizer.py` (NEW)
  - [ ] Function `sanitize_html(html: str) -> str`
  - [ ] Parse HTML with `html5lib` or `BeautifulSoup`
  - [ ] Remove forbidden elements: `<script src>`, `<link href>`, `<iframe>`, `<object>`, `<embed>`
  - [ ] Remove dangerous attributes: `onclick`, `onerror`, `onload`, etc.
  - [ ] Validate no `javascript:` protocol in `href` or `src`
  - [ ] Whitelist safe tags (div, span, h1-h6, p, svg, etc.)
  - [ ] Raise exception if unsafe patterns detected

- [ ] **Test**: Generate HTML for "dashboard card" → verify sanitization passes/fails appropriately

### 2.2 Backend: MCP Tool for UI Generation

- [ ] **Directory**: `tools/mcp_visualization_generator/` (NEW)
  - [ ] **File**: `server.py`
    - [ ] MCP server implementation
    - [ ] Tool: `generate_infographic`
    - [ ] Parameters: `description`, `data?`, `style?`
    - [ ] Call `html_generator.generate_html()`
    - [ ] Call `html_sanitizer.sanitize_html()`
    - [ ] Return `{type: "custom_ui", html: sanitized_html}`
  
  - [ ] **File**: `pyproject.toml`
    - [ ] Dependencies: `mcp`, `openai`, `html5lib` or `beautifulsoup4`
  
  - [ ] **File**: `README.md`
    - [ ] Usage instructions
    - [ ] Security considerations

- [ ] **Configuration**: `agents/dreamfarm-agent/.env`
  - [ ] Add `MCP_VISUALIZATION_SERVER_URL=http://localhost:5003` (or appropriate port)
  - [ ] Add `ENABLE_CUSTOM_UI=true`

- [ ] **File**: `agents/dreamfarm-agent/src/routes/responses.py` (MODIFY)
  - [ ] Add `generate_infographic` tool to tools array
  - [ ] Handle custom_ui response type in streaming output

- [ ] **Test**: Call tool with "create card with stats" → verify HTML returned and sanitized

### 2.3 Frontend: Sandboxed UI Renderer

- [ ] **File**: `frontend/src/lib/sanitize.ts` (NEW)
  - [ ] Function `escapeSrcDoc(html: string): string`
  ```typescript
  export function escapeSrcDoc(html: string): string {
    return html
      .replace(/&/g, '&amp;')      // First: escape ampersands
      .replace(/"/g, '&quot;')     // Then: escape quotes
      .replace(/'/g, '&apos;');    // Single quotes
  }
  ```

- [ ] **File**: `frontend/src/components/Messages/CustomUIMessage.tsx` (NEW)
  - [ ] Component props: `{ html: string, metadata?: object }`
  - [ ] Escape HTML using `escapeSrcDoc()`
  - [ ] Render in iframe with `srcDoc` attribute
  - [ ] Set `sandbox="allow-scripts"` (minimal permissions)
  - [ ] Auto-adjust iframe height based on content
  - [ ] Add loading state
  - [ ] Add error boundary
  ```tsx
  <iframe
    srcDoc={escapeSrcDoc(html)}
    sandbox="allow-scripts"
    style={{
      width: '100%',
      height: `${height}px`,
      border: '1px solid var(--border)',
      borderRadius: '8px'
    }}
    onLoad={handleLoad}
    title="Generated Visualization"
  />
  ```

- [ ] **File**: `frontend/src/components/Messages/MessageRenderer.tsx` (MODIFY)
  - [ ] Detect `custom_ui` content type
  - [ ] Render using CustomUIMessage component

- [ ] **Test**: Send custom_ui message → verify renders in sandboxed iframe

### 2.4 Frontend: Content Security Policy

- [ ] **File**: `frontend/public/index.html` (MODIFY)
  - [ ] Add CSP meta tag (or configure in server):
  ```html
  <meta http-equiv="Content-Security-Policy" 
        content="default-src 'self'; script-src 'self' 'unsafe-inline'; 
                 style-src 'self' 'unsafe-inline'; frame-src 'self' blob:;" />
  ```

- [ ] **File**: Generated HTML (in html_generator.py)
  - [ ] Inject CSP meta tag in generated HTML:
  ```html
  <meta http-equiv="Content-Security-Policy" 
        content="default-src 'none'; script-src 'unsafe-inline'; 
                 style-src 'unsafe-inline';" />
  ```

- [ ] **Test**: Verify CSP blocks external resources in generated UI

---

## Phase 3: Security Testing & Validation

### 3.1 Security Tests

- [ ] **Test**: XSS via code interpreter
  - [ ] Upload CSV with `<script>alert('xss')</script>` in cell
  - [ ] Verify not executed when displayed

- [ ] **Test**: XSS via generated HTML
  - [ ] Request UI with description containing malicious code
  - [ ] Verify sanitizer removes/escapes dangerous elements
  - [ ] Try: `<script>`, `<img onerror>`, `<a href="javascript:">`, event handlers

- [ ] **Test**: Iframe sandbox escape attempts
  - [ ] Generated HTML tries `window.parent.document`
  - [ ] Verify blocked by sandbox

- [ ] **Test**: HTML bomb / resource exhaustion
  - [ ] Request extremely large HTML (mega-nested divs)
  - [ ] Verify size limits enforced
  - [ ] Verify rendering doesn't freeze UI

- [ ] **Test**: Code interpreter container isolation
  - [ ] Try to access filesystem outside `/mnt/data`
  - [ ] Try network requests (if blocked)
  - [ ] Verify container timeout works

### 3.2 Functional Tests

- [ ] **Test**: Multi-turn conversation with code interpreter
  - [ ] Upload file → analyze
  - [ ] Follow-up: "Now show monthly averages"
  - [ ] Verify context maintained (same container)

- [ ] **Test**: Combined workflow
  - [ ] Upload CSV → analyze → generate chart
  - [ ] Request custom dashboard card based on results
  - [ ] Verify both code interpreter and custom UI work together

- [ ] **Test**: File types
  - [ ] CSV parsing
  - [ ] Excel (XLSX) parsing
  - [ ] Image analysis
  - [ ] PDF text extraction

---

## Phase 4: Documentation & Polish

### 4.1 Documentation

- [ ] **File**: `lessons/L06_adhoc_coding/README.md` (UPDATE)
  - [ ] Overview of features
  - [ ] Usage examples
  - [ ] Security model explanation
  - [ ] Known limitations

- [ ] **File**: `agents/dreamfarm-agent/README.md` (UPDATE)
  - [ ] Code interpreter setup instructions
  - [ ] Environment variables
  - [ ] Example prompts

- [ ] **File**: `frontend/README.md` (UPDATE)
  - [ ] Custom UI message rendering
  - [ ] File upload component

### 4.2 User-Facing Features

- [ ] **Error Handling**: Friendly error messages for:
  - [ ] File too large
  - [ ] Unsupported file type
  - [ ] Code execution timeout
  - [ ] HTML generation failure

- [ ] **Loading States**:
  - [ ] File upload progress bar
  - [ ] "Analyzing data..." indicator during code execution
  - [ ] "Generating visualization..." during UI generation

- [ ] **UX Polish**:
  - [ ] Smooth animations for custom UI reveal
  - [ ] Copy button for generated HTML (advanced users)
  - [ ] Download button for generated charts
  - [ ] Responsive design for all custom UIs

### 4.3 Demo Scenarios

- [ ] **Scenario 1: Weight Tracking**
  - [ ] Upload `weight_tracking.csv`
  - [ ] "Analyze my weight data and show trends"
  - [ ] "Create a dashboard card with my progress stats"

- [ ] **Scenario 2: Sales Analysis** (optional)
  - [ ] Create `sales_data.csv` with product sales
  - [ ] "Show me top 5 products by revenue"
  - [ ] "Make an infographic comparing Q1 vs Q2 sales"

- [ ] **Scenario 3: Farm Yield** (domain-specific)
  - [ ] Upload `harvest_data.csv`
  - [ ] "Calculate average yield per hectare"
  - [ ] "Create a visual comparison of organic vs conventional crops"

---

## Phase 5: Monitoring & Observability

### 5.1 Logging & Metrics

- [ ] **File**: `agents/dreamfarm-agent/src/services/telemetry.py` (MODIFY)
  - [ ] Log code interpreter calls: duration, code lines, outputs
  - [ ] Log custom UI generation: model, duration, HTML size
  - [ ] Emit DF_META events:
  ```python
  {
    "type": "code_interpreter_call",
    "duration_ms": 2300,
    "code_lines": 15,
    "outputs": ["chart.png"],
    "container_id": "cntr_abc123"
  }
  
  {
    "type": "custom_ui_generated",
    "generator_model": "gpt-4o",
    "html_size_bytes": 1024,
    "sanitized": true
  }
  ```

- [ ] **Monitoring Dashboard** (if applicable):
  - [ ] Track code interpreter usage
  - [ ] Track custom UI generation success rate
  - [ ] Track file upload volumes

---

## Phase 6: Optional Enhancements (Future Work)

### 6.1 Advanced Features (Not in L06 Scope)

- [ ] **Template Library**: Pre-built HTML templates for common visualizations
- [ ] **Interactive Components**: WebSocket for generated UI to send data back
- [ ] **Persistent Containers**: Keep containers alive across sessions
- [ ] **Multi-step Workflows**: Auto-chain code interpreter → UI generation
- [ ] **Version Control**: Save/restore previous generated UIs
- [ ] **Accessibility Audit**: Ensure generated HTML meets WCAG standards

---

## Checklist Summary

### Phase 1: Code Interpreter (Core)
- [ ] 1.1 Enable code_interpreter tool in backend
- [ ] 1.2 File upload endpoint
- [ ] 1.3 File upload UI component
- [ ] 1.4 Display code execution results
- [ ] 1.5 Demo CSV and E2E test

### Phase 2: Custom UI Generation
- [ ] 2.1 HTML generator service with sanitizer
- [ ] 2.2 MCP tool for UI generation
- [ ] 2.3 Sandboxed iframe renderer in frontend
- [ ] 2.4 Content Security Policy setup

### Phase 3: Security & Validation
- [ ] 3.1 XSS prevention tests
- [ ] 3.2 Functional multi-turn tests

### Phase 4: Documentation & Polish
- [ ] 4.1 Update READMEs
- [ ] 4.2 Error handling and UX
- [ ] 4.3 Demo scenarios

### Phase 5: Monitoring
- [ ] 5.1 Logging and DF_META events

---

## Implementation Order (Recommended)

1. **Day 1**: Phase 1.1-1.2 (Backend code interpreter + file upload)
2. **Day 1-2**: Phase 1.3-1.4 (Frontend file upload + results display)
3. **Day 2**: Phase 1.5 (Demo CSV + E2E test code interpreter)
4. **Day 3**: Phase 2.1 (HTML generator + sanitizer)
5. **Day 3-4**: Phase 2.2 (MCP tool integration)
6. **Day 4**: Phase 2.3 (Frontend iframe renderer)
7. **Day 4**: Phase 2.4 (CSP setup)
8. **Day 5**: Phase 3 (Security testing)
9. **Day 5**: Phase 4 (Documentation + polish)
10. **Day 5**: Phase 5 (Monitoring)

---

## Notes for Coding Agent

### Critical Security Reminders
- Always sanitize HTML on backend before sending to frontend
- Use `escapeSrcDoc()` to properly escape HTML in iframe srcdoc
- Set minimal iframe sandbox permissions (`allow-scripts` only)
- Enforce CSP headers at both application and iframe level
- Validate file uploads (type, size) before processing
- Never trust LLM-generated code without validation

### Code Standards (per AGENTS.md)
- Use docstrings for all public functions
- No progress comments in code
- Update `docs/ImplementationLog.md` with architectural decisions
- Prefix temporary scripts with `adhoc_` and delete after use
- Keep component READMEs up to date

### Testing Strategy
- Unit tests for sanitizer (critical security component)
- Integration tests for code interpreter workflow
- E2E tests for user journey
- Security tests for XSS/sandbox escape attempts

---

## Success Criteria

✅ User can upload CSV file and get data analysis with charts  
✅ User can request custom dashboard UI and see it rendered safely  
✅ All security tests pass (no XSS, sandbox escape, etc.)  
✅ Demo scenario (weight tracking) works end-to-end  
✅ Documentation updated in Design.md and relevant READMEs  
✅ DF_META events emitted for observability  

---

**Ready for implementation by coding agent!**
