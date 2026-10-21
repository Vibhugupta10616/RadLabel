import { createContext, useCallback, useContext, useRef, useState, type ReactNode } from 'react'
import { api } from './api'
import type { Report, UploadInput } from './contract'

// Reports live only in memory: a page reload starts over, by design ("never stored").
export type SessionState =
  | { status: 'idle' }
  | { status: 'loading'; count: number }
  | { status: 'error'; message: string }
  | { status: 'ready'; sessionId: string; reports: Report[]; sample: boolean }

const Ctx = createContext<{ state: SessionState; start: (input: UploadInput) => void; retry: () => void } | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<SessionState>({ status: 'idle' })
  const last = useRef<UploadInput>({})

  const start = useCallback(async (input: UploadInput) => {
    last.current = input
    setState({ status: 'loading', count: input.sample ? 5 : (input.files?.length ?? 0) + (input.text ? 1 : 0) })
    try {
      const { session_id } = await api.createSession()
      const { reports } = await api.uploadReports(session_id, input)
      if (!reports.length) throw new Error('No report text was found in what you uploaded.')
      setState({ status: 'ready', sessionId: session_id, reports, sample: !!input.sample })
    } catch (e) {
      setState({ status: 'error', message: (e as Error).message })
    }
  }, [])

  return <Ctx.Provider value={{ state, start, retry: () => start(last.current) }}>{children}</Ctx.Provider>
}

export const useSession = () => useContext(Ctx)!
