import { useQuery } from '@tanstack/react-query'
import { getCases, getCase, getTimeline, getRisks, getSummary, getDocuments } from '@/lib/api'
import type { Case, CaseSummary, Document, RisksResponse, TimelineResponse } from '@/lib/types'

// ─── All cases ────────────────────────────────────────────────────────────────

export function useCases() {
  return useQuery<Case[], Error>({
    queryKey: ['cases'],
    queryFn: getCases,
  })
}

// ─── Single case ──────────────────────────────────────────────────────────────

export function useCase(id: string | undefined) {
  return useQuery<Case, Error>({
    queryKey: ['cases', id],
    queryFn: () => getCase(id!),
    enabled: !!id,
  })
}

// ─── Documents for a case ─────────────────────────────────────────────────────

export function useDocuments(caseId: string | undefined) {
  return useQuery<Document[], Error>({
    queryKey: ['documents', caseId],
    queryFn: () => getDocuments(caseId!),
    enabled: !!caseId,
  })
}

// ─── Case intelligence ────────────────────────────────────────────────────────

export function useSummary(caseId: string | undefined) {
  return useQuery<CaseSummary, Error>({
    queryKey: ['summary', caseId],
    queryFn: () => getSummary(caseId!),
    enabled: !!caseId,
    staleTime: 5 * 60_000,   // summaries are expensive — cache 5 min
  })
}

export function useTimeline(caseId: string | undefined) {
  return useQuery<TimelineResponse, Error>({
    queryKey: ['timeline', caseId],
    queryFn: () => getTimeline(caseId!),
    enabled: !!caseId,
    staleTime: 5 * 60_000,
  })
}

export function useRisks(caseId: string | undefined) {
  return useQuery<RisksResponse, Error>({
    queryKey: ['risks', caseId],
    queryFn: () => getRisks(caseId!),
    enabled: !!caseId,
    staleTime: 5 * 60_000,
  })
}
