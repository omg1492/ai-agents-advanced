// Global configuration type
declare global {
  interface Window {
    APP_CONFIG: {
      BACKEND_URL: string;
      API_VERSION: string;
    };
  }
}

// Get runtime configuration
function getConfig() {
  return window.APP_CONFIG || {
    BACKEND_URL: 'http://localhost:8001',
    API_VERSION: 'v1'
  };
}

// API client class for DreamFarm Agent
export class DreamFarmAPI {
  private baseUrl: string;

  constructor() {
    const config = getConfig();
    this.baseUrl = config.BACKEND_URL;
  }

  /**
   * Create a new conversation thread
   */
  async createThread(title?: string) {
    const response = await fetch(`${this.baseUrl}/threads`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ title }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get thread information
   */
  async getThread(threadId: string) {
    const response = await fetch(`${this.baseUrl}/threads/${threadId}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get thread: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Send a message in a thread
   */
  async sendMessage(threadId: string, message: string, abortSignal?: AbortSignal) {
    const response = await fetch(`${this.baseUrl}/threads/${threadId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message }),
      signal: abortSignal,
    });

    if (!response.ok) {
      throw new Error(`Failed to send message: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Get conversation history for a thread
   */
  async getMessages(threadId: string, limit = 50, offset = 0) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

    const response = await fetch(`${this.baseUrl}/threads/${threadId}/messages?${params}`);
    
    if (!response.ok) {
      throw new Error(`Failed to get messages: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Health check
   */
  async healthCheck() {
    const response = await fetch(`${this.baseUrl}/health`);
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }
}

// Default API instance
export const dreamFarmAPI = new DreamFarmAPI();
