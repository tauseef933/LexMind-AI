import axios from 'axios'
import type {
  BillingRecord,
  Case,
  CaseSummary,
  CreateCasePayload,
  Document,
  HearingPrepResponse,
  Message,
  RisksResponse,
  TimelineResponse,
  UploadResponse,
} from './types'

// ─── Axios instance ───────────────────────────────────────────────────────────

const BASE_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 30_000,
})

// Attach API key from env if present (optional header)
const API_KEY = import.meta.env.VITE_API_KEY as string | undefined
if (API_KEY) {
  apiClient.defaults.headers.common['X-API-Key'] = API_KEY
}

// ─── Cases ────────────────────────────────────────────────────────────────────

export async function getCases(): Promise<Case[]> {
  const { data } = await apiClient.get<Case[]>('/cases')
  return data
}

export async function createCase(payload: CreateCasePayload): Promise<Case> {
  const { data } = await apiClient.post<Case>('/cases', payload)
  return data
}

export async function getCase(id: string): Promise<Case> {
  const { data } = await apiClient.get<Case>(`/cases/${id}`)
  return data
}

export async function getMessages(caseId: string): Promise<Message[]> {
  const { data } = await apiClient.get<Message[]>(`/cases/${caseId}/messages`)
  return data
}

export async function deleteCase(id: string): Promise<{ id: string; status: string }> {
  const { data } = await apiClient.delete(`/cases/${id}`)
  return data
}

// ─── Documents ────────────────────────────────────────────────────────────────

export async function getDocuments(caseId: string): Promise<Document[]> {
  const { data } = await apiClient.get<Document[]>(`/cases/${caseId}/documents`)
  return data
}

export async function uploadDocument(
  caseId: string,
  file: File,
  onProgress?: (pct: number) => void,
): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  const { data } = await apiClient.post<UploadResponse>(`/upload?case_id=${caseId}`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (e) => {
      if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
    },
  })
  return data
}

export async function deleteDocument(
  caseId: string,
  docId: string,
): Promise<{ doc_id: string; status: string }> {
  const { data } = await apiClient.delete(`/cases/${caseId}/documents/${docId}`)
  return data
}

// ─── Case intelligence ────────────────────────────────────────────────────────

export async function getSummary(caseId: string): Promise<CaseSummary> {
  const { data } = await apiClient.get<CaseSummary>(`/cases/${caseId}/summary`)
  return data
}

export async function getTimeline(caseId: string): Promise<TimelineResponse> {
  const { data } = await apiClient.get<TimelineResponse>(`/cases/${caseId}/timeline`)
  return data
}

export async function getRisks(caseId: string): Promise<RisksResponse> {
  const { data } = await apiClient.get<RisksResponse>(`/cases/${caseId}/risks`)
  return data
}

export async function startHearingPrep(
  caseId: string,
  hearingDate: string,
): Promise<HearingPrepResponse> {
  const { data } = await apiClient.post<HearingPrepResponse>(`/cases/${caseId}/prep`, {
    hearing_date: hearingDate,
  })
  return data
}

// ─── Analytics ────────────────────────────────────────────────────────────────

export async function getBilling(caseId?: string): Promise<BillingRecord[]> {
  const params = caseId ? { case_id: caseId } : {}
  const { data } = await apiClient.get<BillingRecord[]>('/analytics/billing', { params })
  return data
}

// ─── Streaming chat (raw fetch — SSE) ────────────────────────────────────────
// The actual SSE reading logic lives in useStreaming.ts.
// This helper returns the raw Response so the hook controls the reader.

export function openChatStream(
  content: string,
  caseId: string,
  caseName: string,
): Promise<Response> {
  return fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(API_KEY ? { 'X-API-Key': API_KEY } : {}),
    },
    body: JSON.stringify({ content, case_id: caseId, case_name: caseName }),
  })
}
