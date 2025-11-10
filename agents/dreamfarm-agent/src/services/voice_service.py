"""Voice/Realtime API service for speech-to-speech conversations.

Implements WebSocket-based voice interaction using OpenAI's Realtime API.
Handles audio streaming, tool execution, and transcript persistence with
``mode='voice'`` flag.

For Azure OpenAI the service uses :class:`~openai.AsyncAzureOpenAI` with
``api_version=2025-04-01-preview`` (latest Realtime preview as of October 2025).
For first-party OpenAI it falls back to :class:`~openai.AsyncOpenAI`.
The voice client is intentionally separate from the text chat client to avoid
cross-contaminating API versions.
"""
from __future__ import annotations

import base64
import json
import logging
import asyncio
import os
from typing import Optional, Dict, Any, List

from openai import AsyncOpenAI
from src.services.config_service import AppConfig
from src.services.conversation_store import ConversationStore
from src.services.memory_search_service import MemorySearchService
from src.services.user_profile_service import UserProfileService

logger = logging.getLogger(__name__)


class VoiceService:
    """Service for managing voice/realtime API interactions.
    
    Key responsibilities:
    - Establish and manage WebSocket connection to OpenAI Realtime API
    - Filter tools appropriately for voice mode (memory_search only by default)
    - Persist transcripts with mode='voice' flag
    - Handle real-time audio streaming
    """

    def __init__(
        self,
        config: AppConfig,
        conversation_store: Optional[ConversationStore] = None,
        memory_search_service: Optional[MemorySearchService] = None,
        agentic_search_service: Optional[Any] = None,  # Add agentic search
        user_profile_service: Optional[UserProfileService] = None,
    ):
        """Initialize voice service.
        
        Creates a separate AsyncOpenAI client specifically for the Realtime API
        with api-version=2025-08-28 (required for Realtime), independent from
        the text chat client.
        
        Args:
            config: Application configuration
            conversation_store: Optional conversation persistence service
            memory_search_service: Optional memory search service
            agentic_search_service: Optional agentic search service (semantic/keyword)
            user_profile_service: Optional user profile service
        """
        self.config = config
        self.conversation_store = conversation_store
        self.memory_search = memory_search_service
        self.agentic_search = agentic_search_service
        self.user_profile = user_profile_service
        
        # Get voice-specific model (separate from text chat model)
        # For Azure: This should be your realtime deployment name
        # For OpenAI: Use the standard realtime model
        self.model_name = os.getenv("VOICE_MODEL") or config.openai.model_name or "gpt-4o-realtime-preview-2024-12-17"
        
        # Create Realtime API client with correct API version (2025-04-01-preview)
        # This is separate from the text chat client which uses 'preview'
        api_key = config.openai.api_key
        base_url = config.openai.base_url
        self._api_version = "2025-04-01-preview"
        self._is_azure = bool(base_url)
        
        if base_url:
            # Azure OpenAI: Realtime API requires api-version=2025-04-01-preview
            azure_endpoint = base_url.rstrip("/")
            if azure_endpoint.lower().endswith("/openai/v1"):
                azure_endpoint = azure_endpoint[: -len("/openai/v1")]

            try:
                from openai import AsyncAzureOpenAI  # type: ignore
            except ImportError as exc:  # pragma: no cover - import guard
                raise RuntimeError(
                    "AsyncAzureOpenAI requires the openai package with Azure extras."
                ) from exc

            self.client = AsyncAzureOpenAI(
                api_key=api_key,
                azure_endpoint=azure_endpoint,
                api_version=self._api_version,
            )
            logger.info(
                "VoiceService initialized (Azure) with model=%s api_version=%s endpoint=%s",
                self.model_name,
                self._api_version,
                azure_endpoint,
            )
        else:
            # OpenAI hosted: No api-version needed
            self.client = AsyncOpenAI(api_key=api_key)
            logger.info(
                "VoiceService initialized (OpenAI) with model=%s",
                self.model_name
            )

    def get_voice_tools(self, enable_heavy_tools: bool = False) -> List[Dict[str, Any]]:
        """Get filtered tools for voice mode.
        
        By default, enables memory_search AND agentic search (semantic/keyword)
        to keep latency low. Heavy graph tools can be enabled via flag.
        
        Args:
            enable_heavy_tools: If True, enables all tools (graph search, etc.)
            
        Returns:
            List of tool definitions
        """
        tools: List[Dict[str, Any]] = []
        
        # Memory search - always allowed in voice mode
        if self.memory_search and self.memory_search.enabled:
            tools.append({
                "type": "function",
                "name": "memory_search",
                "description": "Search user's past conversation summaries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for past conversations"
                        },
                        "k": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 5,
                            "description": "Number of memories to retrieve (1-5)"
                        }
                    },
                    "required": ["query"]
                }
            })
        
        # Agentic search (semantic and keyword) - enabled by default for product queries
        if self.agentic_search and self.agentic_search.enabled:
            tools.append({
                "type": "function",
                "name": "semantic_product_search",
                "description": "Search products using semantic similarity. Best for natural language queries about products.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language search query for products"
                        },
                        "k": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Number of products to retrieve"
                        }
                    },
                    "required": ["query"]
                }
            })
            tools.append({
                "type": "function",
                "name": "keyword_product_search",
                "description": "Search products using keyword matching. Fast and precise for specific product names or terms.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of keywords to search for in product names/descriptions"
                        },
                        "k": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "description": "Number of products to retrieve"
                        }
                    },
                    "required": ["keywords"]
                }
            })
        
        # Heavy tools only if explicitly enabled (off by default for voice)
        if enable_heavy_tools:
            logger.info("Heavy tools enabled for voice session")
            # Could add graph search here if needed
            pass
        
        return tools

    async def handle_voice_session(
        self,
        websocket: Any,
        thread_id: str,
        user_id: str,
        system_prompt: Optional[str] = None,
        enable_heavy_tools: bool = False,
    ) -> None:
        """Handle a voice conversation session via WebSocket.
        
        Args:
            websocket: FastAPI WebSocket connection
            thread_id: Conversation thread ID
            user_id: Authenticated user ID
            system_prompt: Optional system instructions
            enable_heavy_tools: Enable heavy tools (graph search, etc.)
        """
        # Build voice-appropriate tools
        tools = self.get_voice_tools(enable_heavy_tools)
        
        # Track transcript for persistence
        transcript: List[Dict[str, str]] = []
        
        try:
            # Connect to OpenAI Realtime API
            async with self.client.beta.realtime.connect(
                model=self.model_name
            ) as connection:
                logger.info(
                    "Voice session started: thread=%s user=%s tools=%d",
                    thread_id, user_id, len(tools)
                )
                
                # Configure session with latest API format
                # Note: 'type' should NOT be in session_config - it's handled by the SDK
                session_config: Dict[str, Any] = {
                    "modalities": ["text", "audio"],
                    "instructions": (system_prompt or "You are a helpful assistant.") + " Speak naturally in Czech with proper Czech pronunciation and intonation.",
                    "voice": "coral",  # Natural female voice, may sound better for Czech than alloy
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1",
                        "language": "cs",  # Czech language hint for better transcription quality
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": 0.5,
                        "prefix_padding_ms": 300,
                        "silence_duration_ms": 500,
                        "create_response": True,
                        "interrupt_response": True,  # Automatically interrupt response when user speaks
                    },
                }

                # Azure: NO type/model in session (passed to connect() instead)
                # Note: output_modalities parameter has been removed from the Realtime API
                # The 'modalities' field (set above on line 240) already controls both input and output

                # Add tools if available
                if tools:
                    session_config["tools"] = tools

                # Debug: Log the exact session config being sent
                logger.debug("Sending session config (Azure=%s): %s", self._is_azure, json.dumps(session_config, indent=2))

                # Both Azure and OpenAI use session.update(), but the SDK handles the protocol differences
                await connection.session.update(session=session_config)
                
                # Bidirectional streaming loop
                async def forward_from_client():
                    """Forward audio from client WebSocket to OpenAI."""
                    try:
                        chunk_count = 0
                        while True:
                            # Receive data from client
                            message = await websocket.receive()
                            
                            # Handle different message types
                            if "bytes" in message:
                                # Raw audio data - forward to Realtime API
                                data = message["bytes"]
                                if data:
                                    audio_b64 = base64.b64encode(data).decode("utf-8")
                                    await connection.input_audio_buffer.append(audio=audio_b64)
                                    chunk_count += 1
                                    if chunk_count % 50 == 0:
                                        logger.debug(f"Forwarded {chunk_count} audio chunks to Realtime API")
                            elif "text" in message:
                                # JSON control message from client
                                text_msg = message["text"]
                                try:
                                    data = json.loads(text_msg)
                                    msg_type = data.get("type")
                                    
                                    if msg_type == "input_audio_buffer.append":
                                        # Audio buffer append (base64 encoded)
                                        audio_b64 = data.get("audio")
                                        if audio_b64:
                                            await connection.input_audio_buffer.append(audio=audio_b64)
                                            chunk_count += 1
                                            if chunk_count % 50 == 0:
                                                logger.debug(f"Forwarded {chunk_count} audio chunks to Realtime API")
                                    elif msg_type == "input_audio_buffer.commit":
                                        # Commit the audio buffer
                                        logger.info("Committing audio buffer")
                                        await connection.input_audio_buffer.commit()
                                    elif msg_type == "response.create":
                                        # Trigger a response from the assistant
                                        logger.info("Creating response")
                                        await connection.response.create()
                                    elif msg_type == "response.cancel":
                                        # Cancel in-progress response (for interruption)
                                        logger.info("Canceling response due to user interruption")
                                        await connection.response.cancel()
                                    elif text_msg == "stop":
                                        logger.info("Received stop signal from client")
                                        break
                                except json.JSONDecodeError:
                                    # Not JSON, check for simple commands
                                    if text_msg == "stop":
                                        logger.info("Received stop signal from client")
                                        break
                            else:
                                logger.debug("Received unknown message type, breaking")
                                break
                    except Exception as e:
                        logger.warning("Client forward error: %s", e)
                
                async def forward_to_client():
                    """Forward events from OpenAI to client WebSocket."""
                    try:
                        async for event in connection:
                            event_type = getattr(event, "type", "")
                            
                            # Audio response delta (PCM16 audio bytes)
                            if event_type in {"response.audio.delta", "response.output_audio.delta"}:
                                delta = getattr(event, "delta", None)
                                if delta:
                                    try:
                                        audio_bytes = base64.b64decode(delta)
                                        await websocket.send_bytes(audio_bytes)
                                    except Exception as de:
                                        logger.warning("Audio decode error: %s", de)
                            
                            # Audio transcript (what the assistant said)
                            elif event_type in {
                                "response.audio_transcript.delta",
                                "response.output_audio_transcript.delta",
                            }:
                                # Delta events accumulate; final transcript handled in .done event
                                pass
                            
                            elif event_type in {
                                "response.audio_transcript.done",
                                "response.output_audio_transcript.done",
                            }:
                                transcription = getattr(event, "transcript", "")
                                if transcription:
                                    transcript.append({
                                        "role": "assistant",
                                        "content": transcription,
                                        "mode": "voice"
                                    })
                                    logger.debug("Assistant audio transcript: %s", transcription[:50])
                            
                            # User input transcript
                            elif event_type == "conversation.item.input_audio_transcription.completed":
                                transcription = getattr(event, "transcript", "")
                                if transcription:
                                    transcript.append({
                                        "role": "user",
                                        "content": transcription,
                                        "mode": "voice"
                                    })
                                    logger.debug("User transcript: %s", transcription[:50])
                            
                            # Response text output (in case text modality used)
                            elif event_type in {"response.text.done", "response.output_text.done"}:
                                text = getattr(event, "text", "")
                                if text:
                                    transcript.append({
                                        "role": "assistant",
                                        "content": text,
                                        "mode": "voice"
                                    })
                                    logger.debug("Assistant text: %s", text[:50])
                            
                            # Function calls
                            elif event_type == "response.function_call_arguments.done":
                                await self._handle_function_call(event, connection, user_id)
                            
                            # Session events
                            elif event_type == "session.created":
                                logger.info("Realtime session created")
                            
                            elif event_type == "session.updated":
                                logger.debug("Realtime session updated")
                            
                            # Error events
                            elif event_type == "error":
                                error_msg = getattr(event, "error", {})
                                logger.error("Realtime API error: %s", error_msg)
                            
                            # Forward event to client (for debugging/logging)
                            # Convert event to dict safely
                            try:
                                if hasattr(event, "model_dump"):
                                    event_data = event.model_dump()
                                else:
                                    event_data = {"type": event_type}
                                
                                await websocket.send_json({
                                    "type": event_type,
                                    "data": event_data
                                })
                            except Exception as je:
                                logger.debug("Event JSON serialization skipped: %s", je)
                    
                    except Exception as e:
                        logger.warning("Server forward error: %s", e)
                
                # Run both directions concurrently
                await asyncio.gather(
                    forward_from_client(),
                    forward_to_client(),
                    return_exceptions=True
                )
        
        except Exception as e:
            logger.error("Voice session error: %s", e)
            raise
        
        finally:
            # Persist transcript when session ends
            if transcript and self.conversation_store:
                try:
                    for msg in transcript:
                        self.conversation_store.upsert_message(
                            thread_id=thread_id,
                            user_id=user_id,
                            message=msg
                        )
                    logger.info(
                        "Persisted voice transcript: thread=%s messages=%d",
                        thread_id, len(transcript)
                    )
                except Exception as pe:
                    logger.error("Failed to persist voice transcript: %s", pe)

    async def _handle_function_call(
        self,
        event: Any,
        connection: Any,
        user_id: str
    ) -> None:
        """Handle function call execution during voice session.
        
        Args:
            event: Function call event from Realtime API
            connection: Realtime API connection
            user_id: Authenticated user ID
        """
        call_id = getattr(event, "call_id", None)
        name = getattr(event, "name", None)
        arguments = getattr(event, "arguments", "{}")
        
        if not call_id or not name:
            logger.warning("Function call missing call_id or name")
            return
        
        logger.info("Executing function call: name=%s call_id=%s", name, call_id)
        
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except Exception as e:
            logger.warning("Failed to parse function arguments: %s", e)
            args = {}
        
        output = {}
        
        # Execute memory_search
        if name == "memory_search" and self.memory_search:
            try:
                output_json = await self.memory_search.execute(args, user_id=user_id)
                output = json.loads(output_json)
                logger.info("Memory search completed: %d memories found", len(output.get("memories", [])))
            except Exception as e:
                logger.warning("Memory search failed in voice: %s", e)
                output = {"memories": []}
        
        # Execute agentic search (semantic or keyword)
        elif name in ["semantic_product_search", "keyword_product_search"] and self.agentic_search:
            try:
                # Agentic search service handles both semantic and keyword search
                output_json = await self.agentic_search.execute(name, args, user_is_vip=False)
                output = json.loads(output_json)
                logger.info("Agentic search (%s) completed: %d products found", name, len(output.get("products", [])))
            except Exception as e:
                logger.warning("Agentic search (%s) failed in voice: %s", name, e)
                output = {"products": [], "error": str(e)}
        
        else:
            logger.warning("Unknown or unavailable function: %s", name)
            output = {"error": f"Function {name} not available"}
        
        # Submit function output back to Realtime API
        try:
            logger.debug("Submitting function output for call_id=%s", call_id)
            await connection.conversation.item.create(
                item={
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": json.dumps(output)
                }
            )
            # Trigger response generation with the function results
            logger.debug("Triggering response generation after function call")
            await connection.response.create()
            logger.info("Function call completed and response triggered: call_id=%s", call_id)
        except Exception as e:
            logger.error("Failed to submit function output or trigger response: %s", e)
