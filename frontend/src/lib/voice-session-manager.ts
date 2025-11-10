import { dreamFarmAPI } from '@/services/api';

type VoiceStatus = 'idle' | 'connecting' | 'active' | 'error';
type TranscriptHandler = (role: 'user' | 'assistant', text: string) => void;

interface VoiceSessionSnapshot {
	status: VoiceStatus;
	threadId: string | null;
	wsReadyState: number | null;
	isMuted: boolean;
	error: string | null;
	/**
	 * Monotonic timestamp used to help React detect updates via useSyncExternalStore.
	 */
	lastUpdated: number;
}

interface StartVoiceSessionOptions {
	threadId: string | null;
	onTranscript?: TranscriptHandler;
}

// -----------------------------
// Internal mutable state refs
// -----------------------------

const listeners = new Set<() => void>();

let snapshot: VoiceSessionSnapshot = {
	status: 'idle',
	threadId: null,
	wsReadyState: null,
	isMuted: false,
	error: null,
	lastUpdated: Date.now(),
};

let transcriptHandler: TranscriptHandler | null = null;

let ws: WebSocket | null = null;
let audioContext: AudioContext | null = null;
let mediaStream: MediaStream | null = null;
let processor: ScriptProcessorNode | null = null;
let audioQueue: ArrayBuffer[] = [];
let isPlaying = false;
let isResponding = false;
let startInFlight = false;

// -----------------------------
// Utility helpers
// -----------------------------

function publish(partial: Partial<VoiceSessionSnapshot>) {
	snapshot = {
		...snapshot,
		...partial,
		lastUpdated: Date.now(),
	};
	for (const listener of listeners) {
		listener();
	}
}

function getConfig() {
	return window.APP_CONFIG || {
		BACKEND_URL: 'http://localhost:8001',
		API_VERSION: 'v1',
	};
}

function getAuthToken() {
	const tokensStr = localStorage.getItem('df_auth_tokens_v1');
	if (!tokensStr) return null;
	try {
		const tokens = JSON.parse(tokensStr);
		return tokens.access_token as string | undefined;
	} catch (error) {
		console.warn('[VoiceSessionManager] Failed to parse auth tokens', error);
		return null;
	}
}

async function ensureAudioContext(): Promise<AudioContext> {
	if (!audioContext) {
		console.log('[VoiceSessionManager] 🎛️ Creating AudioContext');
		audioContext = new AudioContext({ sampleRate: 24000 });
	}

	if (audioContext.state === 'suspended') {
		console.log('[VoiceSessionManager] 🎚️ Resuming suspended AudioContext');
		await audioContext.resume();
	}

	return audioContext;
}

function getBackendWsUrl() {
	const config = getConfig();
	return config.BACKEND_URL.replace(/^http/, 'ws');
}

function emitTranscript(role: 'user' | 'assistant', text: string) {
	if (!transcriptHandler) {
		console.log('[VoiceSessionManager] 📨 Transcript handler missing, buffering skipped text');
		return;
	}
	transcriptHandler(role, text);
}

function closeMediaResources() {
	if (mediaStream) {
		console.log('[VoiceSessionManager] 🎙️ Stopping microphone tracks');
		mediaStream.getTracks().forEach((track) => track.stop());
		mediaStream = null;
	}

	if (processor) {
		console.log('[VoiceSessionManager] 🔌 Disconnecting ScriptProcessor');
		processor.disconnect();
		processor = null;
	}

	if (audioContext) {
		console.log('[VoiceSessionManager] 🔇 Closing AudioContext');
		audioContext.close();
		audioContext = null;
	}

	audioQueue = [];
	isPlaying = false;
}

function resetSessionState(reason: string) {
	console.log('[VoiceSessionManager] 🔁 Reset session state:', reason);
	ws = null;
	isResponding = false;
	closeMediaResources();
	publish({ status: 'idle', wsReadyState: null });
}

async function playAudioQueue() {
	if (isPlaying || audioQueue.length === 0) return;
	if (!audioContext) return;

	isPlaying = true;
	const ctx = audioContext;

	while (audioQueue.length > 0) {
		const pcm16Data = audioQueue.shift();
		if (!pcm16Data) break;

		try {
			const int16Array = new Int16Array(pcm16Data);
			const float32Array = new Float32Array(int16Array.length);

			for (let i = 0; i < int16Array.length; i += 1) {
				float32Array[i] = int16Array[i] / 32768.0;
			}

			const audioBuffer = ctx.createBuffer(1, float32Array.length, 24000);
			audioBuffer.copyToChannel(float32Array, 0);

			await new Promise<void>((resolve) => {
				const source = ctx.createBufferSource();
				source.buffer = audioBuffer;
				source.connect(ctx.destination);
				source.onended = () => resolve();
				source.start();
			});
		} catch (error) {
			console.error('[VoiceSessionManager] 🔊 Failed to play audio chunk', error);
		}
	}

	isPlaying = false;
}

function setupAudioPipeline(localAudioContext: AudioContext, stream: MediaStream, socket: WebSocket) {
	console.log('[VoiceSessionManager] 🛠️ Setting up audio pipeline');
	const source = localAudioContext.createMediaStreamSource(stream);
	const localProcessor = localAudioContext.createScriptProcessor(4096, 1, 1);
	processor = localProcessor;

	let audioChunksSent = 0;
	localProcessor.onaudioprocess = (event) => {
		if (!socket || socket.readyState !== WebSocket.OPEN) {
			return;
		}

		if (snapshot.isMuted) {
			return;
		}

		const inputData = event.inputBuffer.getChannelData(0);
		const pcm16 = new Int16Array(inputData.length);

		for (let i = 0; i < inputData.length; i += 1) {
			const s = Math.max(-1, Math.min(1, inputData[i]));
			pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
		}

		socket.send(pcm16.buffer);
		audioChunksSent += 1;

		if (audioChunksSent % 50 === 0) {
			console.log('[VoiceSessionManager] 🎧 Sent audio chunks:', audioChunksSent);
		}
	};

	source.connect(localProcessor);
	localProcessor.connect(localAudioContext.destination);
	console.log('[VoiceSessionManager] ✅ Audio pipeline ready');
}

function handleRealtimeJson(event: MessageEvent<string>, socket: WebSocket) {
	try {
		const data = JSON.parse(event.data);

		switch (data.type) {
			case 'input_audio_buffer.speech_started':
				console.log('[VoiceSessionManager] 🗣️ User started speaking');
				if (isResponding && socket.readyState === WebSocket.OPEN) {
					console.log('[VoiceSessionManager] ⛔ Interrupting assistant response');
					socket.send(JSON.stringify({ type: 'response.cancel' }));
				}
				audioQueue = [];
				isPlaying = false;
				break;
			case 'response.created':
				isResponding = true;
				console.log('[VoiceSessionManager] 🤖 Assistant responding');
				break;
			case 'response.done':
			case 'response.cancelled':
				isResponding = false;
				console.log('[VoiceSessionManager] 🤖 Assistant finished responding');
				break;
			case 'conversation.item.input_audio_transcription.completed': {
				const transcript = data.data?.transcription ?? data.transcript ?? data.data?.transcript;
				if (transcript) {
					console.log('[VoiceSessionManager] 👤 User transcript:', transcript);
					emitTranscript('user', transcript);
				}
				break;
			}
			case 'response.audio_transcript.done': {
				const transcript = data.transcript ?? data.data?.transcript;
				if (transcript) {
					console.log('[VoiceSessionManager] 🤖 Assistant transcript:', transcript);
					emitTranscript('assistant', transcript);
				}
				break;
			}
			case 'response.done': {
				const output = data.data?.response?.output;
				if (Array.isArray(output)) {
					for (const item of output) {
						if (item.type === 'message' && Array.isArray(item.content)) {
							for (const content of item.content) {
								if (content.type === 'text' && typeof content.text === 'string') {
									const text = content.text.trim();
									if (!text.startsWith('{') || (!text.includes('"query"') && !text.includes('"keywords"'))) {
										console.log('[VoiceSessionManager] 🤖 Assistant text:', text);
										emitTranscript('assistant', text);
									}
								}
							}
						}
					}
				}
				break;
			}
			case 'response.function_call_arguments.done':
				console.log('[VoiceSessionManager] 🔧 Function call:', data.data?.name || data.name, data.data?.arguments || data.arguments);
				break;
			case 'session.created':
				console.log('[VoiceSessionManager] ✅ Realtime session created');
				break;
			case 'session.updated':
				console.log('[VoiceSessionManager] ✅ Realtime session updated');
				break;
			case 'error':
				console.error('[VoiceSessionManager] ❌ Realtime API error:', data.data ?? data);
				publish({ status: 'error', error: 'Realtime API error' });
				break;
			default:
				break;
		}
	} catch (error) {
		console.error('[VoiceSessionManager] ❌ Failed to parse realtime JSON', error);
	}
}

function attachWebSocketHandlers(socket: WebSocket) {
	let connectionStart = Date.now();

	socket.onopen = () => {
		const elapsed = Date.now() - connectionStart;
		console.log('[VoiceSessionManager] ✅ WebSocket opened in', elapsed, 'ms');
		publish({ status: 'active', wsReadyState: WebSocket.OPEN });

		if (!audioContext || !mediaStream) {
			console.warn('[VoiceSessionManager] Audio context or stream missing on open');
			return;
		}
		setupAudioPipeline(audioContext, mediaStream, socket);
	};

	socket.onmessage = (event) => {
		if (event.data instanceof Blob) {
			event.data.arrayBuffer().then((buffer) => {
				audioQueue.push(buffer);
				void playAudioQueue();
			});
			return;
		}

		handleRealtimeJson(event as MessageEvent<string>, socket);
	};

	socket.onerror = (error) => {
		console.error('[VoiceSessionManager] ❌ WebSocket error', error);
		publish({ status: 'error', wsReadyState: socket.readyState, error: 'WebSocket error' });
	};

	socket.onclose = (event) => {
		console.log('[VoiceSessionManager] 🔌 WebSocket closed', {
			code: event.code,
			reason: event.reason,
			wasClean: event.wasClean,
		});
		resetSessionState('onclose');
	};
}

async function requestMicrophone(): Promise<MediaStream> {
	console.log('[VoiceSessionManager] 🎙️ Requesting microphone access');
	const stream = await navigator.mediaDevices.getUserMedia({
		audio: {
			channelCount: 1,
			sampleRate: 24000,
			echoCancellation: true,
			noiseSuppression: true,
		},
	});

	const tracks = stream.getAudioTracks();
	console.log('[VoiceSessionManager] ✅ Microphone granted', {
		trackCount: tracks.length,
		label: tracks[0]?.label,
		muted: tracks[0]?.muted,
	});

	return stream;
}

async function ensureThread(threadId: string | null) {
	if (threadId) {
		return threadId;
	}

	console.log('[VoiceSessionManager] 📄 Creating new thread for voice conversation');
	const thread = await dreamFarmAPI.createThread('Voice Conversation');
	const newThreadId = thread.thread_id;

	window.dispatchEvent(new CustomEvent('df-thread-created', {
		detail: { thread_id: newThreadId, title: 'Voice Conversation' },
	}));

	return newThreadId;
}

function cleanupWebSocket() {
	if (!ws) return;

	console.log('[VoiceSessionManager] 🔌 Closing WebSocket connection');
	try {
		ws.close();
	} catch (error) {
		console.warn('[VoiceSessionManager] Failed to close WebSocket cleanly', error);
	}
	ws = null;
}

function cleanupResources(reason: string) {
	console.log('[VoiceSessionManager] ♻️ Cleaning resources:', reason);
	cleanupWebSocket();
	closeMediaResources();
	isResponding = false;
	publish({ status: 'idle', wsReadyState: null });
}

// -----------------------------
// Public API
// -----------------------------

/**
 * Subscribe to session updates for useSyncExternalStore consumers.
 */
function subscribe(listener: () => void) {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

/**
 * Retrieve the current snapshot of the voice session state.
 */
function getSnapshot() {
	return snapshot;
}

/**
 * Start a voice session, handling thread creation, auth, audio, and websocket setup.
 */
async function start(options: StartVoiceSessionOptions) {
	const { threadId, onTranscript } = options;
	console.log('[VoiceSessionManager] 🚀 start called', {
		threadId,
		currentStatus: snapshot.status,
		wsReadyState: ws?.readyState,
		startInFlight,
	});

	if (onTranscript) {
		transcriptHandler = onTranscript;
	}

	if (ws && ws.readyState !== WebSocket.CLOSED) {
		console.warn('[VoiceSessionManager] ⚠️ WebSocket already active, ignoring duplicate start');
		publish({ wsReadyState: ws.readyState, status: snapshot.status });
		return snapshot.threadId;
	}

	if (startInFlight) {
		console.warn('[VoiceSessionManager] ⚠️ Start already in progress, ignoring duplicate request');
		return snapshot.threadId;
	}

	startInFlight = true;

	try {
		let activeThreadId = await ensureThread(threadId ?? snapshot.threadId);
		publish({ threadId: activeThreadId, status: 'connecting', error: null });

		const token = getAuthToken();
		if (!token) {
			throw new Error('Missing authentication token');
		}

		audioContext = await ensureAudioContext();
		console.log('[VoiceSessionManager] 🎛️ AudioContext ready', {
			state: audioContext.state,
			sampleRate: audioContext.sampleRate,
			baseLatency: audioContext.baseLatency,
		});

		mediaStream = await requestMicrophone();

		const backendWsUrl = getBackendWsUrl();
		const wsUrl = `${backendWsUrl}/voice/${activeThreadId}?token=${encodeURIComponent(token)}`;
		console.log('[VoiceSessionManager] 🌐 Connecting WebSocket', wsUrl.replace(/token=[^&]+/, 'token=***'));

		ws = new WebSocket(wsUrl);
		publish({ wsReadyState: ws.readyState });
		attachWebSocketHandlers(ws);

		return activeThreadId;
	} catch (error) {
		console.error('[VoiceSessionManager] ❌ Failed to start voice session', error);
		publish({ status: 'error', error: error instanceof Error ? error.message : 'Unknown error' });

		cleanupResources('start-failed');

		if (error instanceof DOMException) {
			if (error.name === 'NotAllowedError') {
				alert('Microphone access denied. Please allow microphone permissions in your browser settings.');
			} else if (error.name === 'NotFoundError') {
				alert('No microphone found. Please connect a microphone and try again.');
			} else {
				alert('Failed to start voice mode. Please check microphone permissions.');
			}
		} else {
			alert('Failed to start voice mode. Please check the console for details.');
		}

		throw error;
	} finally {
		startInFlight = false;
	}
}

/**
 * Stop the current voice session and release audio/WebSocket resources.
 */
function stop(reason: string = 'user-request') {
	console.log('[VoiceSessionManager] 🛑 stop called', { reason, wsReadyState: ws?.readyState });
	cleanupResources(reason);
}

/**
 * Toggle the mute state for outgoing microphone audio.
 */
function toggleMute() {
	const nextMuted = !snapshot.isMuted;
	console.log('[VoiceSessionManager] 🔇 toggleMute', { muted: nextMuted });
	publish({ isMuted: nextMuted });
}

/**
 * Replace the transcript handler with the latest callback from the UI.
 */
function setTranscriptHandler(handler?: TranscriptHandler) {
	transcriptHandler = handler ?? null;
}

/**
 * Expose the underlying WebSocket for diagnostics.
 */
function getWebSocket() {
	return ws;
}

if (typeof window !== 'undefined') {
	window.addEventListener('beforeunload', () => {
		if (ws && ws.readyState !== WebSocket.CLOSED) {
			console.log('[VoiceSessionManager] 💾 beforeunload cleanup');
			cleanupResources('beforeunload');
		}
	});
}

export const voiceSessionManager = {
	subscribe,
	getSnapshot,
	start,
	stop,
	toggleMute,
	setTranscriptHandler,
	getWebSocket,
};

export type { VoiceSessionSnapshot };