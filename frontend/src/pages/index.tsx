import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import {
  Scale,
  Plus,
  FolderOpen,
  ChevronRight,
  Loader2,
  AlertCircle,
  Gavel,
  Users,
  Calendar,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCases } from '@/hooks/useCases'
import { createCase, deleteCase } from '@/lib/api'
import type { Case, CreateCasePayload } from '@/lib/types'

interface NewCaseFormProps {
  onClose: () => void
}

function NewCaseForm({ onClose }: NewCaseFormProps) {
  const queryClient = useQueryClient()
  const [name, setName] = useState('')
  const [client, setClient] = useState('')
  const [court, setCourt] = useState('')

  const mutation = useMutation({
    mutationFn: (payload: CreateCasePayload) => createCase(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
      onClose()
    },
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    mutation.mutate({ name: name.trim(), client: client || undefined, court: court || undefined })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl bg-white border border-slate-200 p-6 shadow-2xl">
        <div className="flex items-center gap-3 mb-5">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#1F3D6E]/10">
            <Gavel className="h-5 w-5 text-[#1F3D6E]" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-slate-900">New Case</h2>
            <p className="text-xs text-slate-500">Create a new matter to begin analysis</p>
          </div>
        </div>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              Case Name <span className="text-red-500">*</span>
            </label>
            <input
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1F3D6E]/20 focus:border-[#1F3D6E]/40 transition-all"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Smith v. Jones"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Client</label>
            <input
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1F3D6E]/20 focus:border-[#1F3D6E]/40 transition-all"
              value={client}
              onChange={(e) => setClient(e.target.value)}
              placeholder="Alice Smith"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Court</label>
            <input
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#1F3D6E]/20 focus:border-[#1F3D6E]/40 transition-all"
              value={court}
              onChange={(e) => setCourt(e.target.value)}
              placeholder="Superior Court, NY"
            />
          </div>

          {mutation.isError && (
            <p className="text-sm text-red-600 flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4" /> Failed to create case.
            </p>
          )}

          <div className="flex gap-3 pt-1">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 rounded-lg border border-slate-200 px-4 py-2.5 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending || !name.trim()}
              className="flex-1 rounded-lg bg-[#1F3D6E] text-white px-4 py-2.5 text-sm font-medium hover:bg-[#163056] disabled:opacity-50 transition-colors"
            >
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin mx-auto" />
              ) : (
                'Create Case'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

function CaseItem({
  case: c,
  isActive,
  onClick,
  onDelete,
  isDeleting,
}: {
  case: Case
  isActive: boolean
  onClick: () => void
  onDelete: () => void
  isDeleting: boolean
}) {
  return (
    <div
      className={cn(
        'group w-full rounded-xl flex items-center gap-1 transition-all',
        isActive ? 'bg-white/15 shadow-sm' : 'hover:bg-white/10',
      )}
    >
      <button
        type="button"
        onClick={onClick}
        className={cn(
          'flex-1 min-w-0 text-left px-3 py-3 flex items-center gap-3',
          isActive ? 'text-white' : 'text-white/70 hover:text-white',
        )}
      >
        <div className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg',
          isActive ? 'bg-white/20' : 'bg-white/10',
        )}>
          <FolderOpen className="h-4 w-4" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium truncate">{c.name}</p>
          {c.client && (
            <p className={cn('text-xs truncate mt-0.5', isActive ? 'text-white/60' : 'text-white/40')}>
              {c.client}
            </p>
          )}
        </div>
        <ChevronRight
          className={cn(
            'h-4 w-4 shrink-0 transition-opacity',
            isActive ? 'opacity-80' : 'opacity-0 group-hover:opacity-50',
          )}
        />
      </button>
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation()
          onDelete()
        }}
        disabled={isDeleting}
        className="shrink-0 p-2 mr-1 rounded-lg text-white/30 hover:text-red-300 hover:bg-red-500/20 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-50"
        title="Delete case"
      >
        {isDeleting ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Trash2 className="h-3.5 w-3.5" />
        )}
      </button>
    </div>
  )
}

export default function IndexPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { data: cases, isLoading, isError } = useCases()
  const [activeCase, setActiveCase] = useState<Case | null>(null)
  const [showNewCase, setShowNewCase] = useState(false)
  const [deletingCaseId, setDeletingCaseId] = useState<string | null>(null)

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteCase(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cases'] })
    },
  })

  function handleSelectCase(c: Case) {
    setActiveCase(c)
  }

  function handleOpenDashboard() {
    if (activeCase) navigate(`/dashboard/${activeCase.id}`)
  }

  async function handleDeleteCase(c: Case) {
    const confirmed = window.confirm(
      `Delete case "${c.name}"? It will be archived and removed from your case list.`,
    )
    if (!confirmed) return

    setDeletingCaseId(c.id)
    try {
      await deleteMutation.mutateAsync(c.id)
      if (activeCase?.id === c.id) setActiveCase(null)
    } catch {
      window.alert('Failed to delete case. Please try again.')
    } finally {
      setDeletingCaseId(null)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <aside className="w-72 shrink-0 flex flex-col lex-sidebar">
        <div className="px-5 py-5 border-b border-white/10">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-white/10">
              <Scale className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white leading-tight">LexMind AI</p>
              <p className="text-[11px] text-white/50 leading-tight">Legal Intelligence</p>
            </div>
          </div>
        </div>

        <div className="px-4 pt-4 pb-2">
          <button
            type="button"
            onClick={() => setShowNewCase(true)}
            className="w-full flex items-center justify-center gap-2 rounded-xl border border-white/20 bg-white/10 px-3 py-2.5 text-sm font-medium text-white hover:bg-white/15 transition-colors"
          >
            <Plus className="h-4 w-4" />
            New Case
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
          {isLoading && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-white/40" />
            </div>
          )}
          {isError && (
            <p className="text-xs text-red-300 px-2 py-4 text-center">Failed to load cases</p>
          )}
          {cases?.map((c) => (
            <CaseItem
              key={c.id}
              case={c}
              isActive={activeCase?.id === c.id}
              onClick={() => handleSelectCase(c)}
              onDelete={() => handleDeleteCase(c)}
              isDeleting={deletingCaseId === c.id}
            />
          ))}
          {cases?.length === 0 && !isLoading && (
            <p className="text-xs text-white/40 text-center py-10 px-4">
              No cases yet. Create your first matter above.
            </p>
          )}
        </div>

        <div className="px-5 py-4 border-t border-white/10">
          <p className="text-[11px] text-white/30">Multi-Agent RAG System</p>
        </div>
      </aside>

      <main className="flex-1 flex flex-col items-center justify-center bg-slate-50 p-8 overflow-y-auto">
        {!activeCase ? (
          <div className="text-center max-w-lg">
            <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-[#1F3D6E]/10 mx-auto mb-6">
              <Scale className="h-10 w-10 text-[#1F3D6E]" />
            </div>
            <h1 className="text-3xl font-bold text-slate-900 mb-3 tracking-tight">
              Legal Intelligence Platform
            </h1>
            <p className="text-slate-500 text-base mb-8 leading-relaxed">
              Analyse case documents, detect risks, build timelines, and research precedents
              with a multi-agent AI system built for legal professionals.
            </p>
            <button
              type="button"
              onClick={() => setShowNewCase(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-[#1F3D6E] text-white px-6 py-3 text-sm font-semibold hover:bg-[#163056] shadow-lg shadow-[#1F3D6E]/20 transition-all"
            >
              <Plus className="h-4 w-4" />
              Create your first case
            </button>
          </div>
        ) : (
          <div className="w-full max-w-xl">
            <div className="rounded-2xl border border-slate-200 bg-white p-8 shadow-xl shadow-slate-200/50">
              <div className="flex items-start justify-between gap-4 mb-6">
                <div className="flex items-start gap-4">
                  <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-[#1F3D6E]/10 shrink-0">
                    <FolderOpen className="h-6 w-6 text-[#1F3D6E]" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-slate-900">{activeCase.name}</h2>
                    {activeCase.client && (
                      <p className="text-sm text-slate-500 flex items-center gap-1.5 mt-1">
                        <Users className="h-3.5 w-3.5" />
                        {activeCase.client}
                      </p>
                    )}
                    {activeCase.court && (
                      <p className="text-sm text-slate-500 flex items-center gap-1.5 mt-0.5">
                        <Gavel className="h-3.5 w-3.5" />
                        {activeCase.court}
                      </p>
                    )}
                    {activeCase.hearing_date && (
                      <p className="text-sm text-slate-500 flex items-center gap-1.5 mt-0.5">
                        <Calendar className="h-3.5 w-3.5" />
                        Hearing: {activeCase.hearing_date}
                      </p>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => handleDeleteCase(activeCase)}
                  disabled={deletingCaseId === activeCase.id}
                  className="shrink-0 flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 transition-colors disabled:opacity-50"
                >
                  {deletingCaseId === activeCase.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Trash2 className="h-3.5 w-3.5" />
                  )}
                  Delete
                </button>
              </div>

              <div className="grid grid-cols-3 gap-3 mb-6">
                {[
                  { label: 'Document Analysis', desc: 'RAG-powered Q&A' },
                  { label: 'Risk Detection', desc: 'Automated review' },
                  { label: 'Legal Research', desc: 'Precedent search' },
                ].map((item) => (
                  <div key={item.label} className="rounded-xl bg-slate-50 border border-slate-100 p-3 text-center">
                    <p className="text-xs font-semibold text-slate-700">{item.label}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{item.desc}</p>
                  </div>
                ))}
              </div>

              <button
                type="button"
                onClick={handleOpenDashboard}
                className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-[#1F3D6E] text-white px-5 py-3 text-sm font-semibold hover:bg-[#163056] shadow-md shadow-[#1F3D6E]/20 transition-all"
              >
                Open Case Workspace
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}
      </main>

      {showNewCase && <NewCaseForm onClose={() => setShowNewCase(false)} />}
    </div>
  )
}
