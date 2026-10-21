// Typed client for the M9a backend. Contract assumptions: web/README.md.
import type { Api } from './contract'
import { mockApi } from './mocks'

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response
  try {
    r = await fetch(`${import.meta.env.VITE_API_BASE ?? ''}/api${path}`, init)
  } catch {
    throw new Error("Couldn't reach the server. Check your connection and try again.")
  }
  if (!r.ok) {
    const body = await r.json().catch(() => null)
    throw new Error(typeof body?.detail === 'string' ? body.detail : `The server returned an error (${r.status}).`)
  }
  return r.json()
}

const json = (body: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})

export const httpApi: Api = {
  createSession: () => call('/session', { method: 'POST' }),
  uploadReports: (id, { text, files = [], sample }) => {
    const form = new FormData()
    if (sample) form.append('sample', 'true')
    if (text) form.append('text', text)
    files.forEach((f) => form.append('files', f))
    return call(`/session/${id}/reports`, { method: 'POST', body: form })
  },
  ask: (id, input) => call(`/session/${id}/ask`, json(input)),
  timeline: (id) => call(`/session/${id}/timeline`),
}

// Mock mode is the default until M9a exists; VITE_MOCK=false switches to the real API.
export const MOCK = import.meta.env.VITE_MOCK !== 'false'
export const api: Api = MOCK ? mockApi : httpApi
