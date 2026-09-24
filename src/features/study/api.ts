import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { authHeader } from '../../lib/auth'
import { API_BASE_URL } from '../../lib/config'
import { api, errorFrom } from '../../lib/http'

export interface StudyTask {
  id: number
  order: number
  ui: 'legacy' | 'console'
  task: string
  decision_id: number
  started: boolean
  decided: boolean
}

export interface StudySession {
  id: number
  participant: string
  participant_number: number
  tasks: StudyTask[]
}

export function useStudySessions() {
  return useQuery({ queryKey: ['study'], queryFn: () => api<StudySession[]>('/api/v1/study/sessions') })
}

export function useStudySession(id: number) {
  return useQuery({
    queryKey: ['study', id],
    queryFn: () => api<StudySession>(`/api/v1/study/sessions/${id}`),
    refetchInterval: 3000, // the participant decides in another screen or in the legacy UI
  })
}

export function useCreateSession() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: (participant: string) => api<StudySession>('/api/v1/study/sessions', { method: 'POST', body: { participant } }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['study'] }),
  })
}

export function startTask(taskId: number) {
  return api<{ id: number; started_at: string }>(`/api/v1/study/tasks/${taskId}/start`, { method: 'POST' })
}

/** The CSV needs the bearer token, so it is fetched and saved rather than linked. */
export async function downloadCsv(): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/v1/study/export.csv`, { headers: await authHeader() })
  if (!response.ok) throw await errorFrom(response)
  const url = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = url
  link.download = 'user_study.csv'
  link.click()
  URL.revokeObjectURL(url)
}
