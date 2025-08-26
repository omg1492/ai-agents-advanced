import { AssistantRuntimeProvider, useLocalRuntime } from '@assistant-ui/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Thread } from '@/components/thread';
import { ThreadList } from '@/components/thread-list';
import { dreamFarmChatAdapter } from './services/chatAdapter';
import './App.css';
import { useEffect, useState } from 'react';
import { buildAuthState, exchangeCode, logout, startLogin, AuthState } from './services/auth';

/**
 * Main App component with DreamFarm AI Assistant
 */
function App() {
  const runtime = useLocalRuntime(dreamFarmChatAdapter);
  const [auth, setAuth] = useState<AuthState>({ loading: true, isAuthenticated: false });

  // Handle redirect callback
  useEffect(() => {
    (async () => {
      const params = new URLSearchParams(window.location.search);
      const code = params.get('code');
      const state = params.get('state');
      if (code && state) {
        await exchangeCode(code, state);
        // Remove query params from URL
        window.history.replaceState({}, document.title, window.location.pathname);
      }
      setAuth(buildAuthState());
    })();
  }, []);

  if (auth.loading) {
    return <div className="h-screen w-screen flex items-center justify-center text-gray-600">Loading...</div>;
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="h-screen w-screen flex flex-col items-center justify-center bg-gray-50 text-center p-6">
        <h1 className="text-3xl font-bold mb-4">🌾 Welcome to Dream Farm</h1>
        <p className="text-gray-600 mb-6 max-w-md">Your AI guide to local farm products. Please sign in to start chatting with the assistant.</p>
        <button onClick={startLogin} className="px-5 py-2.5 rounded-md bg-green-600 text-white hover:bg-green-700 transition">Login with Keycloak</button>
      </div>
    );
  }

  return (
    <TooltipProvider>
      <AssistantRuntimeProvider runtime={runtime}>
        <div className="h-screen w-screen flex flex-col bg-gray-50">
          <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">🌾 Dream Farm AI Assistant</h1>
              <p className="ml-4 text-sm text-gray-600">Your AI-powered marketplace guide</p>
            </div>
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 text-sm text-gray-700">
                <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-green-100 text-green-700 font-semibold">{auth.username?.charAt(0)?.toUpperCase()}</span>
                <span>{auth.username}</span>
                {auth.isVip && (
                  <span className="ml-1 inline-flex items-center rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700 border border-purple-200" title="VIP user">
                    VIP
                  </span>
                )}
              </div>
              <button onClick={logout} className="text-sm px-3 py-1.5 border rounded-md hover:bg-gray-100">Logout</button>
            </div>
          </header>
          <div className="flex-1 flex overflow-hidden">
            <aside className="w-64 bg-white border-r border-gray-200 p-4">
              <ThreadList />
            </aside>
            <main className="flex-1 overflow-hidden">
              <Thread />
            </main>
          </div>
        </div>
      </AssistantRuntimeProvider>
    </TooltipProvider>
  );
}

export default App;
