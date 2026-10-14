import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import '@fontsource-variable/inter/wght.css'
import './index.css'
import './design.css'
import './experience/tokens.css'
import './experience/experience.css'
import './auth/auth.css'
import './components/cursor.css'
import { ConvexReactClient } from 'convex/react'
import { ConvexBetterAuthProvider } from '@convex-dev/better-auth/react'
import { convexAuthClient } from './services/auth'

const convexUrl = (import.meta.env.VITE_CONVEX_URL as string | undefined)?.trim()
if (!convexUrl) throw new Error('VITE_CONVEX_URL is not configured.')
const convex = new ConvexReactClient(convexUrl, { expectAuth: true })

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ConvexBetterAuthProvider client={convex} authClient={convexAuthClient}>
      <App />
    </ConvexBetterAuthProvider>
  </React.StrictMode>,
)
