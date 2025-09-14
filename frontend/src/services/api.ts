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
  private getAuthHeader(): Record<string,string> {
    try {
      const raw = localStorage.getItem('df_auth_tokens_v1');
      if (!raw) return {};
      const { access_token, expires_at } = JSON.parse(raw);
      if (!access_token) return {};
      const now = Math.floor(Date.now()/1000);
      if (now >= (expires_at - 30)) return {};
      return { Authorization: `Bearer ${access_token}` };
    } catch { return {}; }
  }

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
    ...this.getAuthHeader(),
      },
      body: JSON.stringify({ title }),
    });

    if (!response.ok) {
      throw new Error(`Failed to create thread: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * List recent threads (server persists ordering by updated_at desc)
   */
  async listThreads(limit = 10, offset = 0) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    const response = await fetch(`${this.baseUrl}/threads?${params}`, { headers: { ...this.getAuthHeader() }});
    if (!response.ok) {
      throw new Error(`Failed to list threads: ${response.statusText}`);
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
    ...this.getAuthHeader(),
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
   * Send a message and receive a streaming text response
   */
  async sendMessageStream(threadId: string, message: string, abortSignal?: AbortSignal) {
  const response = await fetch(`${this.baseUrl}/threads/${threadId}/messages/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/plain',
    ...this.getAuthHeader(),
      },
      body: JSON.stringify({ message }),
      signal: abortSignal,
    });

    if (!response.ok) {
      throw new Error(`Failed to send message (stream): ${response.statusText}`);
    }

    if (!response.body) {
      throw new Error('Streaming not supported by the browser or no response body');
    }

    return response.body; // ReadableStream<Uint8Array>
  }

  /**
   * Get conversation history for a thread
   */
  async getMessages(threadId: string, limit = 50, offset = 0) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    });

  const response = await fetch(`${this.baseUrl}/threads/${threadId}/messages?${params}`, { headers: { ...this.getAuthHeader() }});
    
    if (!response.ok) {
      throw new Error(`Failed to get messages: ${response.statusText}`);
    }

    return response.json();
  }

  /** Delete (archive) a thread */
  async deleteThread(threadId: string) {
    const response = await fetch(`${this.baseUrl}/threads/${threadId}`, { method: 'DELETE', headers: { ...this.getAuthHeader() }});
    if (!response.ok) {
      throw new Error(`Failed to delete thread: ${response.statusText}`);
    }
    return response.json();
  }

  /** Rename a thread */
  async renameThread(threadId: string, title: string) {
    const payload = { title };
    const response = await fetch(`${this.baseUrl}/threads/${threadId}/title`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...this.getAuthHeader() },
      body: JSON.stringify(payload)
    });
    if (!response.ok) {
      throw new Error(`Failed to rename thread: ${response.statusText}`);
    }
    return response.json();
  }

  /**
   * Health check
   */
  async healthCheck() {
  const response = await fetch(`${this.baseUrl}/health`, { headers: { ...this.getAuthHeader() }});
    
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.statusText}`);
    }

    return response.json();
  }
}

// Default API instance
export const dreamFarmAPI = new DreamFarmAPI();
