import { useEffect, useRef, useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import {
  Send,
  Paperclip,
  X,
  Loader2,
  FileText,
  Scale,
  MessageSquare,
  CheckCircle2,
  Trash2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useStreaming } from '@/hooks/useStreaming'
import { deleteDocument, getDocuments, uploadDocument } from '@/lib/api'
import MessageBubble from './MessageBubble'
import AgentTrace from './AgentTrace'
import DocumentViewer from './DocumentViewer'
import SuggestedQuestions from './SuggestedQuestions'
import type { Case } from '@/lib/types'

interface ChatWindowProps {
  activeCase: Case | null
}

interface UploadState {
  filename: string
  progress: number
  done: boolean
  error: string | null
}

export default function ChatWindow({ activeCase }: ChatWindowProps) {
  const caseId = activeCase?.id ?? null
  const { messages, agentTrace, isStreaming, historyLoading, sendMessage } = useStreaming(caseId)
  const [input, setInput] = useState('')
  const [uploads, setUploads] = useState<UploadState[]>([])
  const [viewer, setViewer] = useState<{ filename: string; page: number } | null>(null)
  const [deletingDocId, setDeletingDocId] = useState<string | null>(null)

  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()

  const { data: documents = [], isLoading: docsLoading } = useQuery({
    queryKey: ['documents', caseId],
    queryFn: () => getDocuments(caseId!),
    enabled: !!caseId,
  })

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
      { filename: file.name, progress: 0, done: false, error: null },
    ])

    try {
      await uploadDocument(activeCase.id, file, (pct) => {
        setUploads((prev) =>
          prev.map((u, i) => (i === idx ? { ...u, progress: pct } : u)),
        )
      })
      setUploads((prev) =>
        prev.map((u, i) => (i === idx ? { ...u, progress: 100, done: true } : u)),
      )
      queryClient.invalidateQueries({ queryKey: ['documents', activeCase.id] })
    } catch {
      setUploads((prev) =>
        prev.map((u, i) => (i === idx ? { ...u, error: 'Upload failed' } : u)),
      )
    }
  }

  async function handleDeleteDocument(docId: string, filename: string) {
    if (!activeCase) return
    const confirmed = window.confirm(`Delete "${filename}" from this case? This cannot be undone.`)
    if (!confirmed) return

    setDeletingDocId(docId)
    try {
      await deleteDocument(activeCase.id, docId)
      if (viewer?.filename === filename) setViewer(null)
      queryClient.invalidateQueries({ queryKey: ['documents', activeCase.id] })
    } catch {
      window.alert('Failed to delete document. Please try again.')
    } finally {
      setDeletingDocId(null)
    }
  }

  const handleCitationClick = useCallback((filename: string, page: number) => {
    setViewer({ filename, page })
  }, [])

  if (!activeCase) {
    return (
      <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
        Select a case to start chatting.
      </div>
    )
  }

  const showSuggestions = !isStreaming

  return (
    <div className="flex flex-1 overflow-hidden bg-slate-50">
      {/* Documents sidebar */}
      <aside className="w-56 shrink-0 flex flex-col border-r border-slate-200 bg-white">
        <div className="px-4 py-3 border-b border-slate-200">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
            Case Files
          </p>
          <p className="text-xs text-slate-500 mt-0.5 truncate">{activeCase.name}</p>
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
                  ? 'bg-[#1F3D6E]/10'
                  : 'hover:bg-slate-50',
              )}
            >
              <button
                type="button"
                onClick={() => setViewer({ filename: doc.filename, page: 1 })}
                className={cn(
                  'flex-1 min-w-0 text-left flex items-start gap-2 px-2.5 py-2 text-xs',
                  viewer?.filename === doc.filename
                    ? 'text-[#1F3D6E]'
                    : 'text-slate-600',
                )}
              >
                <FileText className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                <span className="truncate font-medium">{doc.filename}</span>
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

      {/* Chat column */}
      <div className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <div className="shrink-0 px-5 py-3.5 border-b border-slate-200 bg-[#1F3D6E] flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/10">
            <Scale className="h-4 w-4 text-white" />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-white leading-tight truncate">
              {activeCase.name}
            </p>
            <p className="text-xs text-white/60 leading-tight truncate">
              {[activeCase.client, activeCase.court].filter(Boolean).join(' · ') || 'Active case'}
            </p>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-white/70 bg-white/10 rounded-full px-2.5 py-1">
            <MessageSquare className="h-3 w-3" />
            {messages.length}
          </div>
        </div>

        {uploads.length > 0 && (
          <div className="shrink-0 px-4 py-2 border-b border-slate-200 bg-white flex flex-wrap gap-2">
            {uploads.map((u, i) => (
              <div
                key={i}
                className={cn(
                  'flex items-center gap-2 text-xs rounded-full px-3 py-1 border',
                  u.error
                    ? 'bg-red-50 border-red-200 text-red-700'
                    : u.done
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700'
                    : 'bg-blue-50 border-blue-200 text-blue-700',
                )}
              >
                <FileText className="h-3 w-3 shrink-0" />
                <span className="max-w-[120px] truncate">{u.filename}</span>
                {!u.done && !u.error && <span className="tabular-nums">{u.progress}%</span>}
                {u.done && (
                  <span className="flex items-center gap-0.5">
                    <CheckCircle2 className="h-3 w-3" /> Ingesting
                  </span>
                )}
                {u.error && <span>{u.error}</span>}
                <button
                  type="button"
                  onClick={() => setUploads((prev) => prev.filter((_, j) => j !== i))}
                  className="ml-0.5 rounded-full hover:opacity-70"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex-1 overflow-y-auto py-5 space-y-4">
          {historyLoading && (
            <div className="flex items-center justify-center gap-2 text-sm text-slate-400 py-8">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading conversation…
            </div>
          )}

          {!historyLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center gap-4 text-center px-8 py-6">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[#1F3D6E]/10">
                <Scale className="h-7 w-7 text-[#1F3D6E]" />
              </div>
              <div>
                <p className="text-base font-semibold text-slate-800">Start your case analysis</p>
                <p className="text-sm text-slate-500 max-w-sm mt-1">
                  Upload case documents, then ask questions or pick a suggested question below.
                </p>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              onCitationClick={handleCitationClick}
            />
          ))}

          <AgentTrace steps={agentTrace} isStreaming={isStreaming} />
          <div ref={bottomRef} />
        </div>

        {showSuggestions && (
          <SuggestedQuestions
            onSelect={(q) => submitMessage(q)}
            disabled={isStreaming}
          />
        )}

        <div className="shrink-0 border-t border-slate-200 bg-white px-4 py-3">
          <div className="flex items-end gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 focus-within:ring-2 focus-within:ring-[#1F3D6E]/20 focus-within:border-[#1F3D6E]/40 transition-all">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="shrink-0 mb-1 rounded-lg p-1.5 text-slate-400 hover:text-[#1F3D6E] hover:bg-[#1F3D6E]/5 transition-colors"
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
                  ? 'bg-[#1F3D6E] text-white hover:bg-[#163056]'
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
          <p className="text-[11px] text-slate-400 mt-1.5 text-center">
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
    </div>
  )
}
