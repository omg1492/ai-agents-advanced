import { createRoot } from 'react-dom/client'
import App from './App.tsx'
import './index.css'

// NOTE: StrictMode disabled because it causes issues with WebSocket ref persistence
// in VoiceButton component. Strict Mode's double-mount behavior interferes with
// async WebSocket connection lifecycle, causing state/ref mismatches.
// See: https://react.dev/reference/react/StrictMode
createRoot(document.getElementById('root')!).render(
  <App />
)
