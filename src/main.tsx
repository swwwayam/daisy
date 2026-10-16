import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import AppBoundary from './components/AppBoundary'
import '@fontsource-variable/inter/wght.css'
import './index.css'
import './design.css'
import './experience/tokens.css'
import './experience/experience.css'
import './auth/auth.css'
import './components/cursor.css'
import './workspace/enhancements.css'
import { ConvexReactClient } from 'convex/react'
import { ConvexBetterAuthProvider } from '@convex-dev/better-auth/react'
import { convexAuthClient, authConfigurationError } from './services/auth'

const convexUrl = (import.meta.env.VITE_CONVEX_URL as string | undefined)?.trim()
let configurationError = authConfigurationError
let convex: ConvexReactClient | null = null
try {
  if (!convexUrl) throw new Error('Set VITE_CONVEX_URL and restart the frontend.')
  convex = new ConvexReactClient(convexUrl, { expectAuth: true })
} catch { configurationError = 'DAISY cannot connect because its deployment URL is missing or invalid. Check VITE_CONVEX_URL and VITE_CONVEX_SITE_URL, then restart the frontend.' }

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {configurationError || !convex ? <main className="app-recovery"><h1>DAISY needs a connection setting</h1><p>{configurationError}</p><button className="pill pill-solid" onClick={() => window.location.reload()}>Retry after configuration</button></main> : <AppBoundary><ConvexBetterAuthProvider client={convex} authClient={convexAuthClient}>
      <App />
    </ConvexBetterAuthProvider></AppBoundary>}
  </React.StrictMode>,
)
