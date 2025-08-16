"""Minimal thread models for session handles.

These models support a lightweight /threads API that only manages a client-side
session handle (thread_id). Conversation state is kept on the provider via the
Responses API (`store` + `previous_response_id`).
"""

from pydantic import BaseModel
from typing import Optional, List


class CreateThreadRequest(BaseModel):
	"""Request to create a new thread/session."""

	title: Optional[str] = None


class CreateThreadResponse(BaseModel):
	"""Response with created thread info."""

	thread_id: str
	title: str
	created_at: str
	updated_at: str


class Thread(BaseModel):
	"""Thread metadata returned by GET /threads/{thread_id}."""

	thread_id: str
	title: str
	created_at: str
	updated_at: str
	message_count: int


class Message(BaseModel):
	"""Minimal message for history listing."""

	message_id: str
	thread_id: str
	role: str  # "user" | "assistant"
	content: str
	timestamp: str


class SendMessageRequest(BaseModel):
	"""Request to send a new user message."""

	message: str


class SendMessageResponse(BaseModel):
	"""Response containing the assistant reply."""

	message_id: str
	thread_id: str
	user_message: str
	assistant_response: str
	timestamp: str


class GetMessagesResponse(BaseModel):
	"""Paginated message history for a thread."""

	thread_id: str
	messages: List[Message]
	total_count: int

