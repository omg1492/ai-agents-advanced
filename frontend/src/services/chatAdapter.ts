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

  /**
   * Ensure we have a thread to work with
   */
  private async ensureThread(): Promise<string> {
    if (!this.currentThreadId) {
      const thread = await dreamFarmAPI.createThread('New Conversation');
      this.currentThreadId = thread.thread_id;
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

    // Request a streaming response
    const stream = await dreamFarmAPI.sendMessageStream(threadId, userMessage.content, abortSignal);
    const reader = stream.getReader();
    const decoder = new TextDecoder();

  let fullText = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        if (!chunk) continue;
        fullText += chunk;
    yield { content: [{ type: 'text' as const, text: fullText }] };
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

  // Final content to ensure completion state, then end generator
  yield { content: [{ type: 'text' as const, text: fullText }] };
  return; // end generator
  }

  /**
   * Reset the adapter (create new thread)
   */
  reset() {
    this.currentThreadId = null;
  }

  /**
   * Get current thread ID
   */
  getCurrentThreadId(): string | null {
    return this.currentThreadId;
  }
}

// Default adapter instance
export const dreamFarmChatAdapter = new DreamFarmChatAdapter();
