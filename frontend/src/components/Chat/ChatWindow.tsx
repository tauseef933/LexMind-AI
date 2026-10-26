import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Send,
  Paperclip,
  Loader2,
  FileText,
  Scale,
  Trash2,
  Sparkles,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import { cn, normalizeFilename } from '@/lib/utils'
import { useStreaming } from '@/hooks/useStreaming'
import { deleteDocument, getDocuments, uploadDocument } from '@/lib/api'
import { useConfirm, useToast } from '@/lib/feedback'
import { readFlag, writeFlag } from '@/lib/storage'
import CaseDashboard from '@/components/Dashboard/CaseDashboard'
import MessageBubble from './MessageBubble'
import AgentTrace from './AgentTrace'
import DocumentViewer from './DocumentViewer'
import SuggestedQuestions, { SuggestedQuestionCards } from './SuggestedQuestions'
import { useSuggestions } from '@/hooks/useCases'
import type { Case } from '@/lib/types'

const FILES_KEY = 'lexmind.files.open'

interface ChatWindowProps {
  activeCase: Case | null
}

interface UploadState {
  filename: string
  progress: number
}

export default function ChatWindow({ activeCase }: ChatWindowProps) {
  const caseId = activeCase?.id ?? null
  const { messages, agentTrace, isStreaming, historyLoading, sendMessage } = useStreaming(caseId)
  const [input, setInput] = useState('')
  const [uploads, setUploads] = useState<UploadState[]>([])
  const [viewer, setViewerState] = useState<{ filename: string; page: number } | null>(null)
  const [showInsights, setShowInsights] = useState(false)
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null)
  const [filesOpen, setFilesOpen] = useState(() => readFlag(FILES_KEY, true))
  const toast = useToast()
  const confirm = useConfirm()

  function toggleFiles() {
    setFilesOpen((open) => {
      writeFlag(FILES_KEY, !open)
      return !open
    })
  }

  // The document viewer and the insights panel share the right-hand column
  const setViewer = useCallback((next: { filename: string; page: number } | null) => {
    setViewerState(next)
    if (next) setShowInsights(false)
  }, [])

  function toggleInsights() {
    setShowInsights((open) => {
      if (!open) setViewerState(null)
      return !open
    })
  }

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ['documents', caseId],
    queryFn: () => getDocuments(caseId!),
    enabled: !!caseId,
    // Poll while any document is still being ingested
    refetchInterval: (query) =>
      query.state.data?.some((d) => d.status === 'pending' || d.status === 'processing')
        ? 2000
        : false,
  })

  // Older documents have no status; treat them as indexed
  const readyDocs = documents.filter((d) => d.status === 'ready' || d.status == null).length
  const { data: suggestionData, isLoading: suggestionsLoading } = useSuggestions(
    caseId ?? undefined,
    readyDocs,
  )

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, agentTrace])

  function handleInputChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setInput(e.target.value)
    const el = e.target
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`
  }

  const submitMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim()
      if (!trimmed || isStreaming || !activeCase) return
      setInput('')
      if (textareaRef.current) textareaRef.current.style.height = 'auto'
      await sendMessage(trimmed, activeCase.id, activeCase.name)
    },
    [isStreaming, activeCase, sendMessage],
  )

  async function handleSend() {
    await submitMessage(input)
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file || !activeCase) return
    e.target.value = ''

    const idx = uploads.length
    setUploads((prev) => [
      ...prev,
      { filename: file.name, progress: 0 },
    ])

    try {
      await uploadDocument(activeCase.id, file, (pct) => {
        setUploads((prev) =>
          prev.map((u, i) => (i === idx ? { ...u, progress: pct } : u)),
        )
      })
      queryClient.invalidateQueries({ queryKey: ['documents', activeCase.id] })
      toast({
        title: 'Document uploaded',
        description: `${file.name} is being indexed — progress shows in the file list.`,
        variant: 'success',
      })
    } catch {
      toast({ title: 'Upload failed', description: file.name, variant: 'error' })
    } finally {
      // The file list shows indexing status from here on
      setUploads((prev) => prev.filter((_, i) => i !== idx))
    }
  }

  async function handleDeleteDocument(docId: string, filename: string) {
    if (!activeCase) return
    const confirmed = await confirm({
      title: `Delete "${filename}"?`,
      message: 'The file and its search index will be removed from this case. This cannot be undone.',
      confirmLabel: 'Delete file',
      destructive: true,
    })
    if (!confirmed) return

    setDeletingDocId(docId)
    try {
      await deleteDocument(activeCase.id, docId)
      if (viewer?.filename === filename) setViewer(null)
      queryClient.invalidateQueries({ queryKey: ['documents', activeCase.id] })
      toast({ title: 'Document deleted', description: filename, variant: 'success' })
    } catch {
      toast({ title: 'Could not delete the document', description: 'Please try again.', variant: 'error' })
    } finally {
      setDeletingDocId(null)
    }
  }

  const handleCitationClick = useCallback(
    (filename: string, page: number) => {
      // Resolve the cited name to the actual file in this case
      const wanted = normalizeFilename(filename)
      const match = documents.find((d) => normalizeFilename(d.filename) === wanted)
      setViewer({ filename: match?.filename ?? filename, page })
    },
    [setViewer, documents],
  )

  if (!activeCase) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
        Select a case to start chatting.
      </div>
    )
  }

  const indexing = documents.some((d) => d.status === 'pending' || d.status === 'processing')
  const asked = new Set(messages.filter((m) => m.role === 'user').map((m) => m.content.trim()))
  const suggestions = (suggestionData?.questions ?? []).filter((q) => !asked.has(q))

  return (
    <div className="flex flex-1 overflow-hidden bg-slate-50">
      {/* Documents sidebar — collapses to a slim rail */}
      {!filesOpen ? (
        <aside className="flex w-12 shrink-0 flex-col items-center gap-2 border-r border-slate-200 bg-white py-3">
          <button
            type="button"
            onClick={toggleFiles}
            title="Show case files"
            aria-label="Show case files"
            className="rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            <PanelLeftOpen className="h-4 w-4" />
          </button>
          <span
            className="flex h-6 min-w-6 items-center justify-center rounded-full bg-brand-soft px-1.5 text-2xs font-semibold text-brand"
            title={`${documents.length} file(s)`}
          >
            {documents.length}
          </span>
          {indexing && <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-600" aria-label="Indexing" />}
        </aside>
      ) : (
      <aside className="w-60 shrink-0 flex flex-col border-r border-slate-200 bg-white">
        <div className="flex items-center justify-between gap-2 px-4 py-3 border-b border-slate-200">
          <div className="min-w-0">
            <p className="text-2xs font-semibold uppercase tracking-wider text-slate-400">
              Case files
            </p>
            <p className="text-xs text-slate-500 mt-0.5">
              {documents.length} document{documents.length === 1 ? '' : 's'}
            </p>
          </div>
          <div className="flex items-center gap-0.5">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              title="Upload document"
              aria-label="Upload document"
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-brand"
            >
              <Paperclip className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={toggleFiles}
              title="Hide case files"
              aria-label="Hide case files"
              className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
            >
              <PanelLeftClose className="h-4 w-4" />
            </button>
          </div>
        </div>
        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {docsLoading && (
            <div className="flex justify-center py-6">
              <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
            </div>
          )}
          {!docsLoading && documents.length === 0 && (
            <p className="text-xs text-slate-400 text-center py-6 px-2">
              No documents yet. Upload a PDF to begin analysis.
            </p>
          )}
          {documents.map((doc) => (
            <div
              key={doc.id}
              className={cn(
                'group flex items-center gap-1 rounded-lg transition-colors',
                viewer?.filename === doc.filename
                  ? 'bg-brand/10'
                  : 'hover:bg-slate-50',
              )}
            >
              <button
                type="button"
                onClick={() => setViewer({ filename: doc.filename, page: 1 })}
                className={cn(
                  'flex-1 min-w-0 text-left flex items-start gap-2 px-2.5 py-2 text-xs',
                  viewer?.filename === doc.filename
                    ? 'text-brand'
                    : 'text-slate-600',
                )}
              >
                <FileText className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{doc.filename}</span>
                  {(doc.status === 'pending' || doc.status === 'processing') && (
                    <span className="flex items-center gap-1 text-2xs text-blue-600">
                      <Loader2 className="h-2.5 w-2.5 animate-spin" /> Indexing…
                    </span>
                  )}
                  {doc.status === 'failed' && (
                    <span className="block truncate text-2xs text-red-600" title={doc.error ?? undefined}>
                      {doc.error ?? 'Indexing failed'}
                    </span>
                  )}
                </span>
              </button>
              <button
                type="button"
                onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                disabled={deletingDocId === doc.id}
                className="shrink-0 p-1.5 mr-1 rounded-md text-slate-300 hover:text-red-600 hover:bg-red-50 opacity-0 group-hover:opacity-100 transition-all disabled:opacity-50"
                title="Delete file"
              >
                {deletingDocId === doc.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Trash2 className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          ))}
        </div>
      </aside>
      )}

      {/* Chat column */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="shrink-0 flex items-center gap-3 border-b border-slate-200 bg-white px-5 py-2">
          <p className="min-w-0 flex-1 truncate text-xs text-slate-500">
            {[
              activeCase.client,
              activeCase.court,
              activeCase.hearing_date && `Hearing ${activeCase.hearing_date}`,
            ]
              .filter(Boolean)
              .join('  ·  ') || 'Ask questions about this case’s documents'}
          </p>
          <button
            type="button"
            onClick={toggleInsights}
            aria-pressed={showInsights}
            className={cn(
              'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors',
              showInsights
                ? 'border-brand bg-brand text-white'
                : 'border-slate-200 text-slate-700 hover:border-brand/30 hover:text-brand',
            )}
          >
            <Sparkles className="h-3.5 w-3.5" />
            Insights
          </button>
        </div>

        {uploads.length > 0 && (
          <div className="shrink-0 flex flex-wrap gap-2 border-b border-slate-200 bg-white px-4 py-2">
            {uploads.map((u, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-3 py-1 text-xs text-blue-700"
              >
                <Loader2 className="h-3 w-3 shrink-0 animate-spin" />
                <span className="max-w-[160px] truncate">{u.filename}</span>
                <span className="tabular-nums">{u.progress}%</span>
              </div>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto px-4 py-6">
          {historyLoading && (
            <div className="flex items-center justify-center gap-2 text-sm text-slate-400 py-8">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading conversation…
            </div>
          )}

          {!historyLoading && messages.length === 0 && (
            <div className="flex flex-col items-center gap-6 px-6 pt-6 pb-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/10">
                <Scale className="h-7 w-7 text-brand" />
              </div>

              {!docsLoading && documents.length === 0 ? (
                <div>
                  <p className="text-base font-semibold text-slate-800">Add your first document</p>
                  <p className="mt-1 max-w-sm text-sm text-slate-500">
                    Upload a contract, pleading or evidence file (PDF, Word or image) and LexMind
                    will index it so you can ask questions with page-cited answers.
                  </p>
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="mt-4 inline-flex items-center gap-2 rounded-xl bg-brand px-4 py-2.5 text-sm font-medium text-white shadow-md shadow-brand/20 hover:bg-brand-hover"
                  >
                    <Paperclip className="h-4 w-4" />
                    Upload document
                  </button>
                </div>
              ) : readyDocs === 0 && indexing ? (
                <div>
                  <p className="text-base font-semibold text-slate-800">Indexing your documents…</p>
                  <p className="mt-1 max-w-sm text-sm text-slate-500">
                    This usually takes a few seconds. Suggested questions will appear when it's done.
                  </p>
                </div>
              ) : (
                <>
                  <div>
                    <p className="text-base font-semibold text-slate-800">What would you like to know?</p>
                    <p className="mt-1 max-w-md text-sm text-slate-500">
                      Pick a question tailored to this case's documents, or type your own below.
                    </p>
                  </div>
                  <SuggestedQuestionCards
                    questions={suggestions}
                    loading={suggestionsLoading}
                    onSelect={(q) => submitMessage(q)}
                    disabled={isStreaming}
                  />
                </>
              )}
            </div>
          )}

          <div className="mx-auto w-full max-w-3xl space-y-5">
            {messages.map((msg) => (
              <MessageBubble
                key={msg.id}
                message={msg}
                caseId={activeCase.id}
                onCitationClick={handleCitationClick}
              />
            ))}

            {/* Live agent activity only while working; afterwards each answer
                carries a compact summary instead */}
            {isStreaming && <AgentTrace steps={agentTrace} isStreaming />}
          </div>
          <div ref={bottomRef} />
        </div>

        {messages.length > 0 && !isStreaming && (
          <SuggestedQuestions
            questions={suggestions}
            onSelect={(q) => submitMessage(q)}
            disabled={isStreaming}
          />
        )}

        <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-3">
          <div className="mx-auto flex max-w-3xl items-end gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:ring-2 focus-within:ring-brand/20 focus-within:border-brand/40 transition-all">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="shrink-0 mb-1 rounded-lg p-1.5 text-slate-400 hover:text-brand hover:bg-brand/5 transition-colors"
              title="Upload document"
              disabled={isStreaming}
            >
              <Paperclip className="h-4 w-4" />
            </button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.jpg,.jpeg,.png,.tiff,.tif,.webp"
              className="hidden"
              onChange={handleFileChange}
            />
            <textarea
              ref={textareaRef}
              rows={1}
              value={input}
              onChange={handleInputChange}
              onKeyDown={handleKeyDown}
              placeholder={
                isStreaming
                  ? 'Agents are working…'
                  : 'Ask about your case documents, evidence, or legal strategy…'
              }
              disabled={isStreaming}
              className="flex-1 resize-none bg-transparent text-sm text-slate-800 focus:outline-none placeholder:text-slate-400 disabled:opacity-50 min-h-[24px]"
            />
            <button
              type="button"
              onClick={handleSend}
              disabled={!input.trim() || isStreaming}
              className={cn(
                'shrink-0 mb-1 rounded-lg p-2 transition-colors',
                input.trim() && !isStreaming
                  ? 'bg-brand text-white hover:bg-brand-hover'
                  : 'text-slate-300 bg-slate-100',
              )}
            >
              {isStreaming ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </button>
          </div>
          <p className="text-2xs text-slate-400 mt-1.5 text-center">
            Enter to send · Shift+Enter for new line · Attach documents with the paperclip
          </p>
        </div>
      </div>

      {viewer && (
        <div className="w-[44%] shrink-0 flex flex-col overflow-hidden border-l border-slate-200">
          <DocumentViewer
            caseId={activeCase.id}
            filename={viewer.filename}
            page={viewer.page}
            onClose={() => setViewer(null)}
          />
        </div>
      )}

      {showInsights && (
        <div className="w-[38%] min-w-[320px] shrink-0 flex flex-col overflow-hidden border-l border-slate-200">
          <CaseDashboard activeCase={activeCase} onClose={() => setShowInsights(false)} />
        </div>
      )}
    </div>
  )
}
