import type { ChatModelAdapter, ThreadMessage } from '@assistant-ui/react';
import { dreamFarmAPI } from './api';

/**
 * Convert assistant-ui ThreadMessage to our backend format
 */
function convertMessage(message: ThreadMessage) {
  // Extract text content from the message
  const textContent = message.content
    .filter((content: any) => content.type === 'text')
    .map((content: any) => content.text)
    .join('\n');

  return {
    role: message.role,
    content: textContent,
  };
}

/**
 * ChatModelAdapter implementation for DreamFarm backend
 */
export class DreamFarmChatAdapter implements ChatModelAdapter {
  private currentThreadId: string | null = null;
  // Cache of loaded messages per thread; re-dispatched on each selection
  private loadedHistory: Record<string, any[] | undefined> = {};
  // Track a lazily created thread that hasn't been announced to UI yet
  private pendingThreadMeta: any | null = null;
  // Track file attachments for next message
  private pendingAttachments: string[] = [];

  /**
   * Add file attachment for next message
   */
  addAttachment(fileId: string) {
    if (!this.pendingAttachments.includes(fileId)) {
      this.pendingAttachments.push(fileId);
    }
  }

  /**
   * Clear pending attachments
   */
  clearAttachments() {
    this.pendingAttachments = [];
  }

  /**
   * Ensure we have a thread to work with
   */
  private async ensureThread(): Promise<string> {
    if (!this.currentThreadId) {
      const thread = await dreamFarmAPI.createThread('New Conversation');
      this.currentThreadId = thread.thread_id;
      // Defer UI announcement until after first response to avoid runtime resets mid-stream
      this.pendingThreadMeta = thread;
    }
    return this.currentThreadId!; // We know it's not null at this point
  }

  /**
   * Run method required by ChatModelAdapter
   */
  async *run({ messages, abortSignal }: { messages: readonly ThreadMessage[]; abortSignal: AbortSignal }) {
    // Ensure we have a thread
    const threadId = await this.ensureThread();

    // Find the last user message
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== 'user') {
      throw new Error('No user message to respond to');
    }

    const userMessage = convertMessage(lastMessage);

    // Request a streaming response with attachments
    const attachments = [...this.pendingAttachments]; // Copy attachments
    this.clearAttachments(); // Clear for next message
    
    const stream = await dreamFarmAPI.sendMessageStream(threadId, userMessage.content, attachments, abortSignal);
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  const META_PREFIX = 'DF_META:';

  let fullText = '';
  let pending = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (!chunk) continue;
        // Build a buffer that may contain multiple lines or partial lines
        const buffer = pending + chunk;
        const lines = buffer.split('\n');
        pending = lines.pop() ?? '';
        for (const line of lines) {
          if (!line) {
            // preserve blank line breaks for markdown formatting
            fullText += "\n";
            yield { content: [{ type: 'text' as const, text: fullText }] };
            continue;
          }
          if (line.startsWith(META_PREFIX)) {
            const jsonStr = line.slice(META_PREFIX.length);
            try {
              const meta = JSON.parse(jsonStr);
              // Broadcast meta event to the app; UI can render separately
              window.dispatchEvent(new CustomEvent('df-meta', { detail: meta }));
            } catch {
              // ignore parse errors
            }
          } else {
            // restore the newline that split removed
            fullText += line + "\n";
            yield { content: [{ type: 'text' as const, text: fullText }] };
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') {
        // Graceful abort: yield what we have so far
    yield { content: [{ type: 'text' as const, text: fullText }] };
    return; // end generator
      }
      throw err;
    } finally {
      reader.releaseLock();
    }

  // Flush any remaining pending text (not meta)
  if (pending && !pending.startsWith(META_PREFIX)) {
    fullText += pending; // last partial line; no extra newline at the end
  }
  // Final content to ensure completion state, then end generator
  yield { content: [{ type: 'text' as const, text: fullText }] };
  // Announce lazily-created thread now that first assistant reply finished streaming
  if (this.pendingThreadMeta && this.pendingThreadMeta.thread_id === threadId) {
    try {
      window.dispatchEvent(new CustomEvent('df-thread-list-add', { detail: this.pendingThreadMeta }));
    } catch { /* ignore */ }
    this.pendingThreadMeta = null;
  }
  return; // end generator
  }

  /**
   * Reset the adapter (create new thread)
   */
  reset() {
    this.currentThreadId = null;
    // Clear the history cache to prevent old messages from showing
    this.loadedHistory = {};
  }

  /**
   * Fully clear internal state (alias for reset plus future fields)
   */
  clearAll() {
    this.reset();
  }

  /**
   * Get current thread ID
   */
  getCurrentThreadId(): string | null {
    return this.currentThreadId;
  }

  /**
   * Manually set current thread id (used when selecting existing thread from server list)
   */
  setThreadId(threadId: string | null) {
    this.currentThreadId = threadId;
  }

  /**
   * Preload existing messages for a selected thread by fetching from backend and emitting
   * synthetic events the UI layer can interpret. For minimal intrusion we dispatch a custom
   * event containing the transcript; Thread component can listen and render static blocks.
   */
  async preloadMessages(threadId: string) {
    if (!threadId) return;
    // If cached, re-dispatch immediately (ensures history shows again when revisiting)
    const cached = this.loadedHistory[threadId];
    if (cached) {
      window.dispatchEvent(new CustomEvent('df-thread-history', { detail: { threadId, messages: cached } }));
      return;
    }
    try {
      const resp = await dreamFarmAPI.getMessages(threadId, 200, 0);
      const msgs = resp?.messages || [];
      this.loadedHistory[threadId] = msgs;
      window.dispatchEvent(new CustomEvent('df-thread-history', { detail: { threadId, messages: msgs } }));
    } catch {
      // ignore for now
    }
  }
}

// Default adapter instance
// Default (initial) adapter instance. App will replace via setCurrentChatAdapter when remounting.
export const dreamFarmChatAdapter = new DreamFarmChatAdapter();
