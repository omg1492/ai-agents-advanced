# API Reference

This document provides complete specifications for all REST and WebSocket API endpoints in the Dream Farm AI platform.

> **Note**: For high-level API overview, see [Design.md](./Design.md#14-api-surface-representative). For deployment configuration, see [DeploymentGuide.md](./DeploymentGuide.md).

---

## Base Configuration

- **DreamFarm Agent Port**: 8001 (main AI agent, LLM logic, sessions, CORS)
- **Frontend Port**: 3000 (default for React/Vite)
- **Base URL**: `http://localhost:8001` (development)
- **Authentication**: Bearer token (when `AUTH_ENABLED=true`) except /health endpoint

All endpoints protected when `AUTH_ENABLED=true` except `/health`.

---

## Table of Contents

- [Chat Endpoints](#chat-endpoints)
- [Thread Management](#thread-management)
- [File Management](#file-management)
- [Voice Interaction](#voice-interaction)
- [Debug Endpoints](#debug-endpoints)
- [Data Models](#data-models)

---

## Chat Endpoints

### POST /chat

Single-endpoint chat using server-side conversation state via Responses API.

**Request Body:**
```json
{
  "message": "string",
  "previous_response_id": "string (optional)"
}
```

**Response:**
```json
{
  "response_id": "string",
  "message": "string",
  "timestamp": "string (ISO 8601)"
}
```

**Notes:**
- Uses Responses API with `store=true` and `previous_response_id` for continuity
- Stream responses may include meta lines prefixed with `DF_META:` containing JSON telemetry
- Clients should display `DF_META` lines separately from assistant text

---

## Thread Management

### POST /threads

Create a new conversation thread.

**Request Body:**
```json
{
  "title": "string (optional)"
}
```

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "title": "string",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

**Notes:**
- If `title` not provided, generates default: "Dream Farm Chat <timestamp>"
- Thread immediately persisted to `conversations_raw` table (when `CONVERSATION_STORE_ENABLED=true`)

---

### GET /threads

List recent conversation threads for authenticated user.

**Query Parameters:**
- `limit`: integer (optional, default: 10, max: 100)
- `offset`: integer (optional, default: 0)

**Response:**
```json
{
  "threads": [
    {
      "thread_id": "string (UUID)",
      "title": "string",
      "created_at": "string (ISO 8601)",
      "updated_at": "string (ISO 8601)",
      "message_count": "integer"
    }
  ],
  "total_count": "integer"
}
```

**Notes:**
- Ordered by `updated_at DESC`
- Pagination via `limit` and `offset`
- Returns only threads owned by authenticated user

---

### GET /threads/{thread_id}

Get thread metadata (title, counts, timestamps).

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "title": "string",
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)",
  "message_count": "integer"
}
```

---

### PUT /threads/{thread_id}/title

Rename (retitle) an existing thread. Only the owning user may rename.

**Request Body:**
```json
{
  "title": "New concise title"
}
```

**Validation:**
- Non-empty after trimming
- Maximum 160 characters

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "title": "New concise title",
  "updated_at": "string (ISO 8601)"
}
```

**Errors:**
- `404` if thread not found (or not owned by user)
- `422` on validation failure

---

### DELETE /threads/{thread_id}

Delete a thread and its persisted raw transcript. Idempotent (second delete returns 404).

**Response:**
```json
{
  "status": "deleted",
  "thread_id": "string (UUID)"
}
```

**Notes:**
- Removes from in-memory caches
- Deletes from `conversations_raw` table (if enabled)
- Idempotent operation

---

### POST /threads/{thread_id}/messages

Send a message in a conversation thread (non-streaming).

**Request Body:**
```json
{
  "message": "string",
  "attachments": ["file_id1", "file_id2"]  // optional, for code interpreter
}
```

**Response:**
```json
{
  "message_id": "string (UUID)",
  "thread_id": "string (UUID)",
  "user_message": "string",
  "assistant_response": "string",
  "timestamp": "string (ISO 8601)"
}
```

**Notes:**
- Supports file attachments for code interpreter (via file_id from `/files/upload`)
- Maintains server-side conversation state using Responses API

---

### POST /threads/{thread_id}/messages/stream

Send a message and stream the assistant response tokens progressively.

**Request Body:**
```json
{
  "message": "string",
  "attachments": ["file_id1"]  // optional
}
```

**Response:**
- Content-Type: `text/plain`
- Streamed chunks of assistant text as they arrive
- May include `DF_META:` lines with JSON telemetry

**Notes:**
- Maintains server-side conversation state using Responses API (store + previous_response_id)
- Uses same prompt template and optional RAG context as non-streaming route
- Appends final assistant message to in-memory history when stream completes

---

### GET /threads/{thread_id}/messages

Get conversation history for a thread (paginated).

**Query Parameters:**
- `limit`: integer (optional, default: 50, max: 100)
- `offset`: integer (optional, default: 0)

**Response:**
```json
{
  "thread_id": "string (UUID)",
  "messages": [
    {
      "message_id": "string (UUID)",
      "thread_id": "string (UUID)",
      "role": "user|assistant",
      "content": "string",
      "timestamp": "string (ISO 8601)"
    }
  ],
  "total_count": "integer"
}
```

---

## File Management

### POST /files/upload

Upload file for code interpreter analysis.

**Request:**
- Content-Type: `multipart/form-data`
- Field name: `file`
- Max size: 30MB (Responses API limit)
- Supported formats: `.csv`, `.xlsx`, `.json`, `.txt`, `.pdf`, images

**Response:**
```json
{
  "file_id": "string",
  "filename": "string",
  "size_bytes": "integer",
  "mime_type": "string",
  "uploaded_at": "string (ISO 8601)"
}
```

**Notes:**
- File uploaded to Azure OpenAI Files API
- `file_id` can be used in message attachments
- Files automatically associated with code_interpreter tool

---

### GET /files/{file_id}/content

Download generated file content from code interpreter.

**Query Parameters:**
- `download_token`: string (optional, alternative to Bearer auth)

**Response:**
- Binary file content with appropriate `Content-Type`
- `Content-Disposition: inline` for images/PDFs
- `Content-Disposition: attachment` for downloads

**Notes:**
- Proxies Azure OpenAI Files API
- Supports both Bearer token and download token authentication
- Download tokens generated for sandbox file URLs during streaming

---

## Voice Interaction

### WS /voice/{thread_id}

Bidirectional voice interaction via WebSocket (OpenAI/Azure Realtime API).

**Connection:**
- Protocol: WebSocket
- URL: `ws://localhost:8001/voice/{thread_id}`
- Authentication: Bearer token in query param `?token=...` (when auth enabled)

**Client → Server Messages:**
```json
{
  "type": "audio",
  "data": "<base64-encoded PCM16 audio>"
}
```

**Server → Client Messages:**
```json
// Transcript (user speech detected)
{
  "type": "transcript",
  "role": "user",
  "text": "string"
}

// Assistant response text
{
  "type": "transcript",
  "role": "assistant",
  "text": "string"
}

// Audio response (PCM16 base64)
{
  "type": "audio",
  "data": "<base64-encoded PCM16 audio>"
}

// Session status
{
  "type": "status",
  "status": "connected|disconnected|error",
  "message": "string (optional)"
}
```

**Audio Specification:**
- **Format**: PCM16
- **Sample Rate**: 24kHz
- **Channels**: Mono
- **Encoding**: Base64

**Features:**
- Server-side VAD (voice activity detection)
- Turn detection triggers response generation
- Interruption support (`speech_started` → cancel in-flight audio)
- Transcripts appended as normal conversation messages
- Minimal tool set for latency (memory_search + optional lightweight product search)

**Notes:**
- Raw audio never persisted (only text transcripts)
- Mute toggles client-side frame suppression without closing session
- Session maintained by OpenAI/Azure Realtime API

See [VoiceInteraction.md](./VoiceInteraction.md) for detailed voice architecture.

---

## Artifacts

### GET /artifacts/{artifact_id}

Retrieve custom HTML visualization artifact.

**Response:**
- Content-Type: `text/html`
- HTML content (sanitized, self-contained)

**Security:**
- Requires Bearer token authentication
- HTML rendered in sandboxed iframe by frontend
- No external scripts or resources allowed

**Notes:**
- Artifacts stored in-memory (ephemeral)
- Generated via MCP visualization generator tool
- Frontend renders with `sandbox="allow-scripts"` iframe

---

## Debug Endpoints

### GET /debug/user-profile/{user_id}

Debug endpoint for user profile inspection.

**Response:**
```json
{
  "user_id": "string",
  "profile": {
    "diet": {},
    "allergens": [],
    "liked_products": [],
    "disliked_products": [],
    "goals": [],
    "notes": []
  },
  "created_at": "string (ISO 8601)",
  "updated_at": "string (ISO 8601)"
}
```

**Notes:**
- Only available when `AUTH_ENABLED=false` or admin role
- Returns full user profile structure

---

## Health Check

### GET /health

Liveness/readiness check.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "string (ISO 8601)"
}
```

**Notes:**
- No authentication required
- Used by container orchestration (Kubernetes probes)

---

## Data Models

### ChatRequest
```python
class ChatRequest(BaseModel):
    message: str
    previous_response_id: Optional[str] = None
```

### ChatResponse
```python
class ChatResponse(BaseModel):
    response_id: str
    message: str
    timestamp: str
```

### Thread
```python
class Thread(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int
```

### CreateThreadRequest
```python
class CreateThreadRequest(BaseModel):
    title: Optional[str] = None
```

### CreateThreadResponse
```python
class CreateThreadResponse(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
```

### ThreadRenameRequest
```python
class ThreadRenameRequest(BaseModel):
    title: constr(min_length=1, max_length=160)
```

### Message
```python
class Message(BaseModel):
    message_id: str
    thread_id: str
    role: str  # "user" | "assistant"
    content: str
    timestamp: str
```

### SendMessageRequest
```python
class SendMessageRequest(BaseModel):
    message: str
    attachments: list[str] = []  # file_ids from /files/upload
```

### SendMessageResponse
```python
class SendMessageResponse(BaseModel):
    message_id: str
    thread_id: str
    user_message: str
    assistant_response: str
    timestamp: str
```

### HealthResponse
```python
class HealthResponse(BaseModel):
    status: str
    timestamp: str
```

---

## Session Lifecycle

The system implements a hybrid session API combining lightweight thread handles with provider-side conversation state via the Responses API:

1. **Create Session**: Frontend calls `POST /threads` to get a session handle (`thread_id`)
2. **Send Messages**: Frontend sends messages via `POST /threads/{thread_id}/messages`
3. **Server-side State**: Backend calls OpenAI Responses API with `store=True` and remembers only the last `response_id` per `thread_id`
4. **Continuity**: Uses `previous_response_id` on next turn to maintain context
5. **History**: Backend maintains in-memory message list for UI display
6. **Persistence**: Optional database persistence for raw conversations (when `CONVERSATION_STORE_ENABLED=true`)

### Benefits of Hybrid Session API

- **Stateless HTTP**: Each request is independent, easier to scale
- **Provider State**: Uses Responses API server-side state via `previous_response_id`
- **OpenAI Compatible**: Aligns with Responses API conversation model
- **Frontend Friendly**: Easy for React to manage conversation state
- **Optional Persistence**: Memory features can be enabled/disabled independently
- **Debugging**: Easy to inspect conversation history

---

## Related Documentation

- [Design.md](./Design.md) - High-level architecture overview
- [ConfigurationReference.md](./ConfigurationReference.md) - Environment variables and feature flags
- [DeploymentGuide.md](./DeploymentGuide.md) - Docker Compose and Kubernetes deployment
- [SecurityModel.md](./SecurityModel.md) - Authentication and authorization
- [VoiceInteraction.md](./VoiceInteraction.md) - Voice/realtime API details
- [MemoryPersonalization.md](./MemoryPersonalization.md) - Memory and user profiles
