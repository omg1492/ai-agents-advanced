import { AssistantRuntimeProvider, useLocalRuntime } from '@assistant-ui/react';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Thread } from '@/components/thread';
import { ThreadList } from '@/components/thread-list';
import { dreamFarmChatAdapter } from './services/chatAdapter';
import './App.css';

/**
 * Main App component with DreamFarm AI Assistant
 */
function App() {
  // Create the runtime with our custom adapter
  const runtime = useLocalRuntime(dreamFarmChatAdapter);

  return (
    <TooltipProvider>
      <AssistantRuntimeProvider runtime={runtime}>
        <div className="h-screen w-screen flex flex-col bg-gray-50">
          {/* Header */}
          <header className="bg-white border-b border-gray-200 px-4 py-3">
            <div className="flex items-center">
              <h1 className="text-xl font-semibold text-gray-900">
                🌾 Dream Farm AI Assistant
              </h1>
              <p className="ml-4 text-sm text-gray-600">
                Your AI-powered marketplace guide
              </p>
            </div>
          </header>

          {/* Main Layout with Sidebar */}
          <div className="flex-1 flex overflow-hidden">
            {/* Thread List Sidebar */}
            <aside className="w-64 bg-white border-r border-gray-200 p-4">
              <ThreadList />
            </aside>

            {/* Chat Interface */}
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
