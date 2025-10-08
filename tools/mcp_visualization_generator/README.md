# MCP Visualization Generator

An MCP (Model Context Protocol) server that generates custom HTML/CSS/JavaScript visualizations using LLM reasoning models. Perfect for creating dynamic UI components, dashboards, infographics, and data visualizations on demand.

## What It Does

This server provides a single powerful tool called `generate_infographic` that:

1. **Takes a natural language description** of what you want to visualize
2. **Uses GPT-5 or other reasoning models** via OpenAI Responses API to generate self-contained HTML
3. **Applies comprehensive security sanitization** to ensure safe rendering
4. **Returns production-ready HTML** that can be embedded in iframes or displayed directly

### Use Cases

- **Dashboard Cards**: Statistics, KPIs, metrics with custom styling
- **Data Visualizations**: Charts, graphs, tables with interactive elements  
- **Infographics**: Visual representations of information and processes
- **Comparison Tables**: Side-by-side product/feature comparisons
- **Interactive Widgets**: Custom UI components with JavaScript functionality
- **Styled Content**: Rich formatted displays beyond standard markdown

## How to Use This MCP

### From an MCP Client (e.g., Claude Desktop, Agent)

Add this server to your MCP client configuration:

```json
{
  "mcpServers": {
    "visualization-generator": {
      "command": "uv",
      "args": ["--directory", "c:\\git\\advanced-ai-applications\\tools\\mcp_visualization_generator", "run", "python", "main.py"],
      "env": {
        "MCP_API_KEY": "your-secret-key",
        "OPENAI_API_KEY": "your-openai-key",
        "OPENAI_MODEL": "gpt-5",
        "OPENAI_BASE_URL": "https://your-resource.openai.azure.com/openai/v1/",
        "OPENAI_API_VERSION": "preview",
        "REASONING_EFFORT": "low"
      }
    }
  }
}
```

### Calling the Tool

Once connected, call the `generate_infographic` tool:

```python
# From an agent or MCP client
result = await mcp_client.call_tool(
    "generate_infographic",
    {
        "description": "Create a dashboard card showing user statistics with a gradient background",
        "data": {
            "total_users": 1250,
            "active_today": 342,
            "growth_rate": "+12.5%",
            "trend": "up"
        },
        "style": "card"
    }
)

# Result contains sanitized HTML
html = result["html"]
# Render in sandboxed iframe: <iframe sandbox="allow-scripts" srcdoc="..."></iframe>
```

### Tool Parameters

- **`description`** (required, string): Natural language description of the visualization you want
  - Be specific about layout, colors, interactions, animations
  - Example: "Create a comparison table with 3 columns, alternating row colors, and hover effects"

- **`data`** (optional, object): Structured data to display
  - Can be nested objects, arrays, numbers, strings
  - Example: `{"users": [{"name": "Alice", "score": 95}, {"name": "Bob", "score": 87}]}`

- **`style`** (optional, string): Visual style hint to guide generation
  - Supported: `card`, `dashboard`, `infographic`, `table`, `chart`, `widget`
  - Example: `"dashboard"` for multi-section layouts

### Response Format

The tool returns a JSON object:

```json
{
  "type": "custom_ui",
  "html": "<!DOCTYPE html>...",
  "metadata": {
    "generator": "responses_api",
    "model": "gpt-5",
    "description": "..."
  }
}
```

Or on error:

```json
{
  "type": "error",
  "error": "Failed to generate visualization: ..."
}
```

## How It Works

### Architecture

```
User Request → MCP Tool → Responses API (GPT-5) → Raw HTML → Sanitizer → Safe HTML → User
```

1. **Input Processing**: Validates description and data parameters
2. **LLM Generation**: Sends structured prompt to OpenAI Responses API with reasoning effort
3. **HTML Extraction**: Parses response to extract generated HTML code
4. **Security Sanitization**: 5-layer validation removes dangerous content
5. **Result Return**: Returns sanitized HTML ready for safe rendering

### Responses API Integration

Uses the [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses) designed for reasoning models:

- **Endpoint**: `POST /responses`
- **Format**: `{instructions: "...", input: "...", reasoning: {effort: "low"}}`
- **Models**: GPT-5, o3, and future reasoning-optimized models
- **No Temperature**: Reasoning models don't support temperature parameter
- **Configurable Effort**: `low` (fast), `medium` (balanced), `high` (thorough)

### Security Model

Implements **defense-in-depth** with 5 security layers:

1. **LLM Prompt Constraints**: System prompt forbids dangerous patterns
2. **Tag Whitelist**: Only 50+ safe HTML5 tags allowed, rejects `<iframe>`, `<object>`, `<embed>`, `<form>`
3. **Attribute Filtering**: Removes 40+ event handlers (`onclick`, `onerror`, etc.)
4. **Protocol Validation**: Blocks `javascript:` URLs, restricts `data:` URIs to images only
5. **Inline Script Analysis**: Warns on dangerous APIs (`eval`, `setTimeout`, `document.write`)

### Generated HTML Characteristics

All generated HTML is:

- **Self-contained**: No external scripts, stylesheets, or CDN dependencies
- **Responsive**: Uses modern CSS (flexbox, grid, media queries)
- **Accessible**: Includes ARIA labels and semantic HTML5
- **Sandboxable**: Safe to render in `<iframe sandbox="allow-scripts">`
- **CSP-ready**: Includes Content-Security-Policy meta tag

## Features

## Features

- ✅ **Reasoning Models**: Optimized for GPT-5, o3, and other reasoning-focused LLMs
- ✅ **Responses API**: Native integration with OpenAI Responses API format
- ✅ **Configurable Effort**: Adjustable reasoning effort (low/medium/high) via environment
- ✅ **Enhanced Security**: 5-layer defense-in-depth sanitization
- ✅ **Self-Contained HTML**: No external scripts, stylesheets, or CDN dependencies
- ✅ **Azure OpenAI Support**: Unified configuration works with both OpenAI and Azure
- ✅ **Flexible Styles**: Supports cards, dashboards, infographics, tables, charts
- ✅ **Production Ready**: Docker support, health checks, comprehensive testing

## Installation

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) package manager (recommended)
- OpenAI API key or Azure OpenAI endpoint

### Local Setup

```bash
# Clone repository
cd c:\git\advanced-ai-applications\tools\mcp_visualization_generator

# Install dependencies
uv sync

# Or install in editable mode
uv pip install -e .
```

## Configuration

Create a `.env` file in the project root:

```bash
# Server Configuration
HOST=0.0.0.0                    # Server bind address
PORT=5003                       # Server port
MCP_CORS_ORIGINS=*              # CORS origins (* or comma-separated list)

# Authentication
MCP_API_KEY=your-secret-key-here  # Required: Bearer token for MCP auth

# OpenAI Configuration (works for both OpenAI and Azure OpenAI)
OPENAI_API_KEY=your-openai-key    # Required: OpenAI or Azure OpenAI key
OPENAI_MODEL=gpt-5                # Model name (gpt-5, o3, gpt-4o, etc.)
REASONING_EFFORT=low              # Reasoning effort: low, medium, high

# Azure OpenAI Specific (only if using Azure)
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/  # Azure endpoint
OPENAI_API_VERSION=preview        # Azure API version (e.g., 2025-04-01-preview)
```

### Configuration Options

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `HOST` | No | `0.0.0.0` | Server bind address |
| `PORT` | No | `5003` | Server port |
| `MCP_CORS_ORIGINS` | No | `*` | CORS origins (use `*` or list) |
| `MCP_API_KEY` | **Yes** | - | Static bearer token for auth |
| `OPENAI_API_KEY` | **Yes** | - | OpenAI or Azure OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o` | Model name for generation |
| `REASONING_EFFORT` | No | `low` | Reasoning effort level |
| `OPENAI_BASE_URL` | No | - | Azure OpenAI endpoint (if using Azure) |
| `OPENAI_API_VERSION` | No | - | Azure API version (if using Azure) |

### Reasoning Effort Levels

- **`low`**: Fast generation (1-5 seconds), suitable for simple visualizations
  - Use for: Basic cards, simple tables, quick prototypes
  
- **`medium`**: Balanced quality and speed (5-15 seconds)
  - Use for: Dashboards, multi-section layouts, moderate complexity
  
- **`high`**: Maximum quality (15-30+ seconds), complex visualizations
  - Use for: Intricate infographics, data-heavy dashboards, custom interactions

## Running the Server

### Local Development

```bash
# Using uv (recommended)
uv run python main.py

# Or using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 5003
```

### Docker Deployment

Build and run as a container:

```bash
# Build the image
docker build -t mcp-visualization-generator .

# Run the container
docker run -d \
  -p 5003:5003 \
  -e MCP_API_KEY=your-key \
  -e OPENAI_API_KEY=your-openai-key \
  -e OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/ \
  -e OPENAI_API_VERSION=preview \
  -e OPENAI_MODEL=gpt-5 \
  -e REASONING_EFFORT=low \
  --name viz-generator \
  mcp-visualization-generator

# Check health
curl http://localhost:5003/health
# Response: OK
```

### Health Check

The server exposes a health check endpoint:

```bash
curl http://localhost:5003/health
# Response: OK
```

## Testing

### Run All Tests

```bash
# Full test suite (15 tests)
uv run pytest tests/ -v

# Integration tests only (2 tests, ~90 seconds with real LLM calls)
uv run pytest tests/test_inmemory.py -v

# Security sanitizer tests only (13 tests, fast)
uv run pytest tests/test_sanitizer.py -v
```

### Remote Server Integration Test

Test against a deployed MCP server (not included in default pytest suite):

```bash
# Test remote deployment
uv run python tests/test_remote_server.py \
  --url https://your-server.example.com/mcp \
  --api-key your-api-key

# Example with actual deployment
uv run python tests/test_remote_server.py \
  --url https://ca-mcp-viz-gen.grayisland-3e7e5fd0.swedencentral.azurecontainerapps.io/mcp \
  --api-key advancedaiapps2025
```

This test:
- Validates health endpoint availability
- Connects via HTTP transport with bearer authentication
- Tests infographic generation without data
- Tests generation with structured data
- Verifies error handling for invalid inputs
- Confirms all data values appear in generated HTML

### Test Coverage

- **Integration Tests** (`test_inmemory.py`): 2 tests using real LLM API calls
  - `test_generate_visualization`: Basic generation without data
  - `test_with_data`: Generation with structured data input

- **Sanitizer Tests** (`test_sanitizer.py`): 13 comprehensive security tests
  - Forbidden tag rejection (`<iframe>`, `<object>`, `<embed>`)
  - External resource blocking (scripts, stylesheets)
  - Event handler removal (40+ dangerous attributes)
  - Protocol validation (`javascript:`, `data:` URIs)
  - Tag whitelist enforcement
  - Comment removal
  - Inline script warnings

## Security Details

### Multi-Layer Defense

The sanitizer implements **defense-in-depth** with 5 independent security layers:

#### 1. LLM Prompt Constraints
System prompt explicitly forbids:
- External resources (CDN, external scripts/styles)
- Dangerous JavaScript APIs (`eval`, `Function`, `document.write`)
- Frame-breaking code (`window.parent`, `window.top`)
- Forbidden HTML tags (`<iframe>`, `<object>`, `<embed>`)

#### 2. HTML Sanitization
BeautifulSoup-based parsing with:
- **Forbidden Tag Rejection**: Immediately fails on `<iframe>`, `<object>`, `<embed>`, `<applet>`, `<form>`
- **External Resource Blocking**: Removes `<script src>` and `<link href>` for stylesheets
- **Comment Removal**: Strips all HTML comments (can hide malicious content)
- **Tag Whitelist**: Only 50+ safe HTML5 tags allowed

#### 3. Attribute Filtering
Removes **40+ dangerous event handlers**:
- Mouse events: `onclick`, `onmouseover`, `ondrag`, `ondragstart`, `ondrop`
- Keyboard events: `onkeydown`, `onkeypress`, `onkeyup`
- Form events: `onsubmit`, `onreset`, `onchange`, `oninput`
- Media events: `onplay`, `onpause`, `onended`, `onloadstart`
- Clipboard events: `oncopy`, `oncut`, `onpaste`
- And many more...

#### 4. Protocol Validation
- **JavaScript Protocol**: Rejects `javascript:` in `href` and `src` attributes
- **Data URI Restrictions**: 
  - `data:` URIs only allowed for `<img>` tags
  - Blocks `data:text/html` (can inject full HTML pages)
  - Allows `data:image/*` for inline images

#### 5. Inline Script Analysis
Warns (doesn't reject) on potentially dangerous patterns:
- `eval()`, `Function()` constructors (code execution)
- `setTimeout()`, `setInterval()` (delayed code execution)
- `document.write()` (can rewrite entire page)
- `window.parent`, `window.top`, `window.opener` (frame breaking)
- `location.replace`, `location.assign` (navigation hijacking)

### Additional Protection

**Recommendation**: Render generated HTML in a sandboxed iframe:

```html
<iframe 
  sandbox="allow-scripts" 
  srcdoc="...sanitized HTML..."
  style="width: 100%; height: 500px; border: none;"
></iframe>
```

This provides an additional security boundary even if sanitization is bypassed.

### Content Security Policy

Generated HTML includes a restrictive CSP meta tag:

```html
<meta http-equiv="Content-Security-Policy" 
      content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline';" />
```

This ensures:
- No external resources can be loaded
- Only inline scripts/styles are allowed
- No form submissions, no plugins, no object embedding

## Example Usage Scenarios

### Scenario 1: User Statistics Dashboard Card

```python
result = await mcp_client.call_tool(
    "generate_infographic",
    {
        "description": "Create a modern dashboard card with gradient background showing user statistics. Include icons and trend indicators.",
        "data": {
            "total_users": 1250,
            "active_today": 342,
            "growth_rate": "+12.5%",
            "trend": "up"
        },
        "style": "card"
    }
)
```

**Output**: Self-contained HTML with CSS gradients, flex layout, and responsive design.

### Scenario 2: Product Comparison Table

```python
result = await mcp_client.call_tool(
    "generate_infographic",
    {
        "description": "Create an interactive comparison table with 3 columns for product features. Use checkmarks for included features, X for excluded. Add hover effects on rows.",
        "data": {
            "products": [
                {"name": "Basic", "price": "$9/mo", "features": ["Feature A", "Feature B"]},
                {"name": "Pro", "price": "$29/mo", "features": ["Feature A", "Feature B", "Feature C"]},
                {"name": "Enterprise", "price": "$99/mo", "features": ["All Features"]}
            ]
        },
        "style": "table"
    }
)
```

**Output**: Styled comparison table with alternating row colors, hover effects, and checkmark/X symbols.

### Scenario 3: Data Visualization Chart

```python
result = await mcp_client.call_tool(
    "generate_infographic",
    {
        "description": "Create a bar chart showing monthly sales data. Use CSS-based bars with smooth animations on load. Include axis labels and values.",
        "data": {
            "months": ["Jan", "Feb", "Mar", "Apr", "May", "Jun"],
            "sales": [12000, 15000, 13000, 18000, 21000, 19000]
        },
        "style": "chart"
    }
)
```

**Output**: Animated CSS bar chart with transitions, responsive layout, and data labels.

### Scenario 4: Process Infographic

```python
result = await mcp_client.call_tool(
    "generate_infographic",
    {
        "description": "Create a step-by-step process infographic with 4 stages. Use numbered circles connected by arrows. Each step has a title and description.",
        "data": {
            "steps": [
                {"title": "Plan", "description": "Define requirements"},
                {"title": "Design", "description": "Create mockups"},
                {"title": "Build", "description": "Develop solution"},
                {"title": "Launch", "description": "Deploy to production"}
            ]
        },
        "style": "infographic"
    }
)
```

**Output**: Visual process flow with CSS arrows, numbered steps, and clear typography.

## Troubleshooting

### Common Issues

**Server won't start**
- ✓ Check `MCP_API_KEY` and `OPENAI_API_KEY` are set in `.env`
- ✓ Verify port 5003 is not already in use
- ✓ Check Python version is 3.12+

**HTML generation fails**
- ✓ Verify OpenAI API key is valid
- ✓ Check model name is correct (`gpt-5`, `gpt-4o`, etc.)
- ✓ For Azure: verify `OPENAI_BASE_URL` ends with `/openai/v1/`
- ✓ For Azure: check `OPENAI_API_VERSION` is valid (e.g., `preview`)

**Sanitization errors**
- ✓ Generated HTML may contain forbidden tags - try with `reasoning_effort=high`
- ✓ Check server logs for specific security violations
- ✓ External resources detected - ensure LLM prompt is being followed

**Integration tests timeout**
- ✓ Increase timeout in test if using `reasoning_effort=high` (can take 30+ seconds)
- ✓ Check network connectivity to OpenAI API
- ✓ Verify rate limits haven't been exceeded

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## API Reference

### Tool: `generate_infographic`

**Parameters:**

```typescript
{
  description: string;  // Required: Natural language description of visualization
  data?: object;        // Optional: Structured data to display
  style?: string;       // Optional: Style hint (card, dashboard, infographic, table, chart)
}
```

**Returns:**

Success response:
```typescript
{
  type: "custom_ui";
  html: string;         // Sanitized HTML ready for rendering
  metadata: {
    generator: "responses_api";
    model: string;      // Model used for generation
    description: string; // Original description
  }
}
```

Error response:
```typescript
{
  type: "error";
  error: string;        // Error message
}
```

## Contributing

### Development Setup

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests with coverage
uv run pytest --cov=. --cov-report=html

# Format code
uv run black .

# Type checking
uv run mypy main.py
```

### Adding New Features

1. Update `main.py` with new functionality
2. Add tests to `tests/` directory
3. Update README with examples
4. Ensure all tests pass
5. Submit PR with description

## License

See the main repository license at [advanced-ai-applications](https://github.com/tkubica12/advanced-ai-applications).

## Related Documentation

- [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [FastMCP Framework](https://github.com/jlowin/fastmcp)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

## Support

For issues, questions, or contributions:
- GitHub Issues: [advanced-ai-applications/issues](https://github.com/tkubica12/advanced-ai-applications/issues)
- Pull Requests: [advanced-ai-applications/pulls](https://github.com/tkubica12/advanced-ai-applications/pulls)

---

**Built with ❤️ using FastMCP, OpenAI Responses API, and Python**

