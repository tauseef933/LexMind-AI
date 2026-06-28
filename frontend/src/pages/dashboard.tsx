import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, Scale, Loader2, Trash2 } from 'lucide-react'
import { useCase } from '@/hooks/useCases'
import { deleteCase } from '@/lib/api'
import ChatWindow from '@/components/Chat/ChatWindow'

export default function DashboardPage() {
  const { caseId } = useParams<{ caseId: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: activeCase, isLoading, isError } = useCase(caseId)
  const [isDeleting, setIsDeleting] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCase(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      navigate('/')
    },
  })

  async function handleDeleteCase() {
    if (!activeCase) return
    const confirmed = window.confirm(
      `Delete case "${activeCase.name}"? It will be archived and removed from your case list.`,
    )
    if (!confirmed) return

    setIsDeleting(true)
    try {
      await deleteMutation.mutateAsync(activeCase.id)
    } catch {
      window.alert('Failed to delete case. Please try again.')
      setIsDeleting(false)
    }
  }

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-slate-50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 text-[#1F3D6E] animate-spin" />
          <p className="text-sm text-slate-500">Loading case…</p>
        </div>
      </div>
    )
  }

  if (isError || !activeCase) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-4 bg-slate-50">
        <p className="text-slate-500">Case not found.</p>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="inline-flex items-center gap-1.5 text-sm text-[#1F3D6E] hover:underline font-medium"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to cases
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-slate-50">
      <header className="shrink-0 flex items-center gap-3 px-4 py-2.5 border-b border-slate-200 bg-white shadow-sm">
        <button
          type="button"
          onClick={() => navigate('/')}
          className="rounded-lg p-1.5 hover:bg-slate-100 transition-colors"
          aria-label="Back to cases"
        >
          <ArrowLeft className="h-4 w-4 text-slate-500" />
        </button>
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[#1F3D6E]">
          <Scale className="h-3.5 w-3.5 text-white" />
        </div>
        <div className="flex-1 flex items-center gap-2 text-sm min-w-0">
          <span className="font-semibold text-slate-800">LexMind AI</span>
          <span className="text-slate-300">/</span>
          <span className="text-slate-500 truncate">{activeCase.name}</span>
        </div>
        <button
          type="button"
          onClick={handleDeleteCase}
          disabled={isDeleting}
          className="shrink-0 flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
        >
          {isDeleting ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Trash2 className="h-3.5 w-3.5" />
          )}
          Delete Case
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <ChatWindow activeCase={activeCase} />
      </div>
    </div>
  )
}
