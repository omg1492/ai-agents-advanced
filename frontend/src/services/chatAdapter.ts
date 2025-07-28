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
  async run({ messages, abortSignal }: { messages: readonly ThreadMessage[]; abortSignal: AbortSignal }) {
    try {
      // Ensure we have a thread
      const threadId = await this.ensureThread();

      // Get the last user message (the one we need to respond to)
      const lastMessage = messages[messages.length - 1];
      if (!lastMessage || lastMessage.role !== 'user') {
        throw new Error('No user message to respond to');
      }

      // Convert to our backend format
      const userMessage = convertMessage(lastMessage);

      // Send the message and get the response
      const response = await dreamFarmAPI.sendMessage(
        threadId,
        userMessage.content,
        abortSignal
      );

      // Return in the format expected by assistant-ui
      return {
        content: [
          {
            type: 'text' as const,
            text: response.assistant_response,
          },
        ],
      };
    } catch (error) {
      // Handle abort errors gracefully
      if (error instanceof Error && error.name === 'AbortError') {
        return {
          content: [
            {
              type: 'text' as const,
              text: '',
            },
          ],
        };
      }
      
      // Re-throw other errors for the UI to handle
      throw error;
    }
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
