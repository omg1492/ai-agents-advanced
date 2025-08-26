# Dream Farm Frontend

A clean, ChatGPT-style interface for the Dream Farm AI marketplace assistant, built with React and assistant-ui.

## Architecture

This frontend implements a simple, reusable chat interface that connects to the DreamFarm Agent backend API. It uses:

- **React 18** - Modern React with hooks and TypeScript
- **assistant-ui** - Pre-built chat components with ChatGPT-like UX
- **Tailwind CSS** - Utility-first CSS framework
- **Vite** - Fast build tool and dev server
- **TypeScript** - Type safety and better developer experience

## Key Features

- 🎯 **ChatGPT-like Interface** - Familiar chat experience using assistant-ui components
- 🔧 **Custom Backend Integration** - LocalRuntime adapter for DreamFarm Agent API
- 🚀 **Runtime Configuration** - Environment-specific settings without rebuilding
- 📱 **Responsive Design** - Works on desktop and mobile devices
- ⚡ **Fast Development** - Hot reload with Vite
- 🐳 **Docker Ready** - Production-ready containerization

## Quick Start

### Prerequisites

- Node.js 18+ and npm
- DreamFarm Agent running on port 8001

### Development Setup

1. **Install dependencies:**
```bash
npm install
```

2. **Initialize assistant-ui components:**
```bash
npx assistant-ui@latest init
```
This command sets up the required shadcn/ui components and assistant-ui configuration.

3. **Configure backend URL:**
Edit `public/config.js` to point to your DreamFarm Agent:
```javascript
window.APP_CONFIG = {
  BACKEND_URL: 'http://localhost:8001',  // DreamFarm Agent URL
  API_VERSION: 'v1'
};
```

4. **Start development server:**
```bash
npm run dev
```

5. **Open browser:**
Navigate to http://localhost:3000

### Production Build

```bash
# Build for production
npm run build

# Preview production build
npm run preview
```

## Runtime Configuration

The frontend uses a runtime configuration pattern that allows the same build to work in different environments. Authentication (Keycloak OIDC) adds additional variables.

### Local Development
Manually edit `public/config.js`:
```javascript
window.APP_CONFIG = {
  BACKEND_URL: 'http://localhost:8001',
  API_VERSION: 'v1',
  KEYCLOAK_URL: 'http://localhost:8080',
  KEYCLOAK_REALM: 'dreamfarm',
  KEYCLOAK_CLIENT_ID: 'dreamfarm-frontend',
  KEYCLOAK_REDIRECT_URI: 'http://localhost:3000/'
};
```

### Docker Deployment
Set environment variables (all optional except BACKEND_URL; defaults reflect local dev):
```bash
REACT_APP_BACKEND_URL=http://your-dreamfarm-agent-url
REACT_APP_API_VERSION=v1
REACT_APP_KEYCLOAK_URL=http://localhost:8080
REACT_APP_KEYCLOAK_REALM=dreamfarm
REACT_APP_KEYCLOAK_CLIENT_ID=dreamfarm-frontend
REACT_APP_KEYCLOAK_REDIRECT_URI=http://localhost:3000/
```

The container startup script automatically generates `config.js` from these variables.

## Architecture Details

### Components Structure

```
src/
├── components/
│   ├── ui/                 # shadcn/ui components (button, tooltip, etc.)
│   ├── thread.tsx          # Main chat thread component
│   ├── thread-list.tsx     # Thread management sidebar
│   ├── markdown-text.tsx   # Markdown rendering component
│   └── tooltip-icon-button.tsx # Reusable tooltip button
├── services/
│   ├── api.ts              # DreamFarm Agent API client
│   └── chatAdapter.ts      # assistant-ui LocalRuntime adapter
├── App.tsx                 # Main application component
├── main.tsx               # React app entry point
└── index.css              # Global styles (Tailwind)
```

### API Integration

The frontend integrates with the DreamFarm Agent API through:

1. **API Client** (`services/api.ts`) - Handles HTTP requests to backend
2. **Chat Adapter** (`services/chatAdapter.ts`) - Converts between assistant-ui and backend formats
3. **LocalRuntime** - assistant-ui runtime that manages chat state

### Thread Management

The chat adapter automatically:
- Creates new conversation threads
- Manages thread lifecycle
- Handles message persistence (via backend)
- Provides error handling and cancellation

## Available Scripts

- `npm run dev` - Start development server with hot reload
- `npm run build` - Build for production
- `npm run preview` - Preview production build locally
- `npm run lint` - Run ESLint for code quality

## Docker Usage

### Build Image
```bash
docker build -t dreamfarm-frontend .
```

### Run Container
```bash
docker run -p 3000:80 \
  -e REACT_APP_BACKEND_URL=http://localhost:8001 \
  -e REACT_APP_API_VERSION=v1 \
  dreamfarm-frontend
```

### Docker Compose
```yaml
version: '3.8'
services:
  frontend:
    build: .
    ports:
      - "3000:80"
    environment:
      - REACT_APP_BACKEND_URL=http://dreamfarm-agent:8001
      - REACT_APP_API_VERSION=v1
    depends_on:
      - dreamfarm-agent
```

## Customization

### Styling
The interface uses Tailwind CSS. Customize colors, fonts, and layout in:
- `tailwind.config.js` - Tailwind configuration
- `src/App.tsx` - Main component styling
- `src/index.css` - Global styles

### Chat Behavior
Modify chat adapter in `src/services/chatAdapter.ts`:
- Message formatting
- Error handling
- Thread management
- Custom features

#### Customizing Initial Messages/Suggestions
Edit `src/components/thread.tsx` in the `ThreadWelcomeSuggestions` component:
```tsx
<ThreadPrimitive.Suggestion
  className="hover:bg-muted/80 flex max-w-sm grow basis-0 flex-col items-center justify-center rounded-lg border p-3 transition-colors ease-in"
  prompt="Your custom prompt here"
  method="replace"
  autoSend
>
  <span className="line-clamp-2 text-ellipsis text-sm font-semibold">
    Display text for the suggestion
  </span>
</ThreadPrimitive.Suggestion>
```

#### Thread Management
The app includes built-in thread management via `ThreadList` component:
- **New Thread Button** - Creates new conversation threads
- **Thread List** - Shows all conversation threads 
- **Thread Archive** - Archive old conversations
- **Thread Switching** - Switch between different conversations

To customize thread behavior, modify `src/components/thread-list.tsx`.

### API Integration
### Authentication (OIDC via Keycloak)

Minimal, dependency‑free PKCE Authorization Code flow has been implemented:

1. Unauthenticated users see a Welcome screen with a Login button.
2. Clicking Login redirects to Keycloak authorization endpoint with PKCE challenge.
3. After consent/login, Keycloak redirects back to `KEYCLOAK_REDIRECT_URI` with `code` & `state`.
4. Frontend exchanges the code for tokens (access + optional ID token), stores them in `localStorage` (`df_auth_tokens_v1`).
5. Username is extracted from the access token (`preferred_username` fallback to email/sub) and shown in header with avatar + Logout.
6. Logout clears storage and calls Keycloak end-session endpoint (front-channel) then returns to app root.

Environment variables controlling auth (runtime via `public/config.js`):

| Variable | Purpose | Example |
|----------|---------|---------|
| KEYCLOAK_URL | Base Keycloak server URL | http://localhost:8080 |
| KEYCLOAK_REALM | Realm name | dreamfarm |
| KEYCLOAK_CLIENT_ID | Public client ID (PKCE) | dreamfarm-frontend |
| KEYCLOAK_REDIRECT_URI | SPA redirect (must be allowed in client) | http://localhost:3000/ |

Docker env counterparts (used by template expansion): `REACT_APP_KEYCLOAK_URL`, `REACT_APP_KEYCLOAK_REALM`, `REACT_APP_KEYCLOAK_CLIENT_ID`, `REACT_APP_KEYCLOAK_REDIRECT_URI`.

Token Usage: Access token is attached as `Authorization: Bearer <token>` automatically in `api.ts`. No refresh logic yet—on expiry user will need to login again (sufficient for current lesson scope).

VIP Indicator: If the user has the realm role `vip` (as assigned by the provisioning script) a small purple "VIP" badge is shown next to the username in the header. Detection logic inspects `realm_access.roles` for `vip` (and will also honor future custom claims `vip` / `is_vip`).

Security Note: This implementation is for local demo purposes—production hardening (refresh token rotation, silent renew, iframe logout, state nonce replay protection enhancements) intentionally deferred.

## Development Tips

1. **Hot Reload**: Changes to components auto-refresh the browser
2. **TypeScript**: Use TypeScript for better development experience
3. **DevTools**: Use React DevTools browser extension for debugging
4. **API Testing**: Test backend API separately using tools like Postman
5. **Error Handling**: Check browser console for API or runtime errors

## Integration with assistant-ui

This frontend leverages assistant-ui's LocalRuntime for:

- ✅ **Built-in State Management** - Automatic message and thread state
- ✅ **Standard UI Components** - Thread, Message, Input components
- ✅ **Message Features** - Copy, regenerate, edit (future)
- ✅ **Error Handling** - Graceful error display
- ✅ **Responsive Design** - Mobile-friendly interface
- ✅ **Accessibility** - ARIA labels and keyboard navigation

The custom ChatModelAdapter bridges between assistant-ui's interface and our DreamFarm Agent API.

## Troubleshooting

### Common Issues

1. **Cannot connect to backend**
   - Check `public/config.js` has correct backend URL
   - Ensure DreamFarm Agent is running on specified port
   - Verify CORS is configured in backend

2. **Messages not sending**
   - Check browser console for API errors
   - Verify backend API endpoints are working
   - Check network tab in browser DevTools

3. **Build errors**
   - Run `npm ci` to clean install dependencies
   - Check Node.js version (18+ required)
   - Clear `node_modules` and reinstall if needed

### Debug Mode

Enable debug logging by adding to `public/config.js`:
```javascript
window.APP_CONFIG = {
  BACKEND_URL: 'http://localhost:8001',
  API_VERSION: 'v1',
  DEBUG: true  // Enable console logging
};
```

## Contributing

1. Follow TypeScript best practices
2. Use Tailwind for styling
3. Keep components focused and reusable
4. Test with the actual backend API
5. Update this README for new features

## License

This project is part of the Advanced AI Applications course.
