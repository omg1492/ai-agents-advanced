# Chef Agent

Specialized culinary services AI agent for Dream Farm marketplace. Connects to the remote Chef Services MCP server to provide intelligent assistance for finding chefs, catering services, checking availability, and booking culinary services.

## Features

- **Chef Search**: Find chefs by specialty, cuisine type, and event requirements
- **Service Search**: Discover catering and culinary services by type and capacity
- **Availability Checking**: Verify chef and service availability for specific dates
- **Pricing Calculation**: Get detailed quotes with complexity and add-on options
- **Order Placement**: Complete bookings with full details and contact information
- **MCP Integration**: Uses remote Chef Services MCP server for all tool execution

## Architecture

The Chef Agent is a stateless FastAPI service that:

1. Receives culinary service queries via REST API
2. Uses OpenAI Responses API with GPT-5 reasoning
3. Connects to remote Chef Services MCP server for tool execution
4. Returns structured responses with booking information

## Setup

### Prerequisites

- Python 3.12+
- `uv` package manager
- Access to OpenAI or Azure OpenAI API
- Chef Services MCP server running (Azure or local)

### Installation

```bash
# Navigate to agent directory
cd agents/chef-agent

# Install dependencies
uv sync

# Copy environment template
cp .env.template .env

# Edit .env with your credentials
# - OPENAI_API_KEY: Your OpenAI/Azure API key
# - OPENAI_BASE_URL: Azure OpenAI endpoint (optional)
# - CHEF_SERVICES_MCP_URL: URL of deployed MCP server
# - CHEF_SERVICES_MCP_API_KEY: Authentication key for MCP server
```

### Configuration

Edit `.env` file:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your-api-key
OPENAI_MODEL=gpt-5
OPENAI_BASE_URL=https://your-resource.openai.azure.com/openai/v1/
OPENAI_API_VERSION=preview
REASONING_EFFORT=low

# Server Configuration
PORT=8002
CORS_ORIGINS=*
LOG_LEVEL=INFO

# Chef Services MCP (remote server)
CHEF_SERVICES_MCP_URL=https://ca-mcp-chef-services.grayisland-3e7e5fd0.swedencentral.azurecontainerapps.io/mcp
CHEF_SERVICES_MCP_API_KEY=advancedaiapps2025
```

## Running

### Development Mode

```bash
cd agents/chef-agent
uv run uvicorn src.main:app --reload --port 8002
```

### Production Mode

```bash
cd agents/chef-agent
uv run python -m src.main
```

## API Endpoints

### Health Check

```bash
curl http://localhost:8002/health
```

Response:
```json
{
  "status": "ok"
}
```

### Query Endpoint

```bash
curl -X POST http://localhost:8002/query \
  -H "Content-Type: application/json" \
  -d '{"message": "I need an Italian chef for a wedding with 50 guests next Saturday"}'
```

Response:
```json
{
  "response": "I'd be happy to help you find an Italian chef for your wedding...",
  "response_id": "resp_abc123..."
}
```

## Testing

### Unit Tests

Test service initialization, configuration, and core logic with mocked dependencies:

```bash
cd agents/chef-agent
uv run pytest tests/test_config_service.py -v
uv run pytest tests/test_openai_service.py -v
uv run pytest tests/test_api.py -v
```

### Integration Tests

Test against live Chef Services MCP server (requires credentials):

```bash
cd agents/chef-agent
uv run pytest tests/test_integration_remote_mcp.py -v
```

### Run All Tests

```bash
cd agents/chef-agent
uv run pytest -v
```

## Example Queries

### Chef Search

```
"Find me a French chef for a private dinner party"
"I need a chef who specializes in vegan cuisine"
"Show me chefs available for a corporate event"
```

### Service Search

```
"What catering services do you have for 30 people?"
"I need meal prep delivery for 2 weeks"
"Find private chef services for Italian cuisine"
```

### Availability & Booking

```
"Is Chef Maria available on December 15th?"
"Check availability for catering service on New Year's Eve"
"I want to book Chef Antonio for my event next month"
```

### Pricing

```
"How much would it cost to hire a chef for 25 guests?"
"Get me a quote for catering with wine pairing for 40 people"
"What's the price for a complex menu with premium ingredients?"
```

## Development

### Project Structure

```
chef-agent/
├── src/
│   ├── main.py              # FastAPI application & system prompt
│   ├── models/              # Pydantic request/response models
│   │   ├── message.py       # Query request/response
│   │   └── health.py        # Health check response
│   └── services/            # Business logic services
│       ├── config_service.py    # Configuration management
│       └── openai_service.py    # OpenAI Responses API client
├── tests/
│   ├── test_config_service.py   # Config tests
│   ├── test_openai_service.py   # Service tests
│   ├── test_api.py              # API endpoint tests
│   └── test_integration_remote_mcp.py  # Integration tests
├── pyproject.toml           # Dependencies & project metadata
├── pytest.ini               # Test configuration
├── .env                     # Environment variables (not in git)
└── .env.template            # Environment template
```

### Adding New Features

1. **Configuration**: Add settings to `ConfigService` and `.env.template`
2. **Models**: Create Pydantic models in `src/models/`
3. **Services**: Implement logic in `src/services/`
4. **API**: Add endpoints in `src/main.py`
5. **Tests**: Write unit and integration tests
6. **Documentation**: Update this README

## Troubleshooting

### MCP Connection Issues

If the agent cannot connect to the MCP server:

1. Verify `CHEF_SERVICES_MCP_URL` is correct
2. Check `CHEF_SERVICES_MCP_API_KEY` matches server configuration
3. Ensure MCP server is running and accessible
4. Test MCP server directly: `curl -H "Authorization: Bearer <key>" <url>/health`

### OpenAI API Errors

If seeing API errors:

1. Verify `OPENAI_API_KEY` is valid
2. Check `OPENAI_BASE_URL` format (should end with `/openai/v1/`)
3. Confirm `OPENAI_API_VERSION` matches your deployment
4. Check model name (`OPENAI_MODEL`) is deployed in your resource

### Tool Execution Failures

If MCP tools fail to execute:

1. Check MCP server logs for errors
2. Verify tool names match (see MCP server documentation)
3. Ensure required parameters are provided
4. Test individual MCP tools with integration tests

## License

Part of the Advanced AI Applications course project.
