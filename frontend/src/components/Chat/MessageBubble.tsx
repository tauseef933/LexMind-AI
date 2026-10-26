import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useState } from 'react'
import { Check, Copy, Scale } from 'lucide-react'
import { getAgentMeta } from '@/lib/agents'
import { cn, formatMessageTime } from '@/lib/utils'
import type { AgentTraceStep, ChatMessage, Source } from '@/lib/types'
import ActionCard from './ActionCard'

// Also accepts \u3010…\u3011 and \uff3b…\uff3d, which some models use instead of [ ]
const CITATION_RE = /[[\u3010\uff3b]Source:\s*([^,\]\u3011\uff3d]+),\s*Page\s*(\d+)[\]\u3011\uff3d]/g
const CITE_PREFIX = '#cite:'

/**
 * Turn "[Source: file.pdf, Page 3]" citations into markdown links with a
 * #cite: href, so the markdown renderer hands them to our link component.
 */
function linkCitations(content: string): string {
  return content.replace(CITATION_RE, (_match, filename: string, page: string) => {
    const name = filename.trim()
    const label = `Source: ${name}, Page ${page}`.replace(/([[\]\\])/g, '\\$1')
    return `[\\[${label}\\]](${CITE_PREFIX}${encodeURIComponent(name)}:${page})`
  })
}

function parseCiteHref(href: string): { filename: string; page: number } | null {
  if (!href.startsWith(CITE_PREFIX)) return null
  const rest = href.slice(CITE_PREFIX.length)
  const sep = rest.lastIndexOf(':')
  if (sep === -1) return null
  return { filename: decodeURIComponent(rest.slice(0, sep)), page: parseInt(rest.slice(sep + 1), 10) || 1 }
}

function SourcePills({
  sources,
  onCitationClick,
}: {
  sources: Source[]
  onCitationClick: (filename: string, page: number) => void
}) {
  // Research sources are plain URLs (already listed in the answer text);
  // only document chunks get a clickable pill.
  // One pill per file + page, even when several chunks of that page were cited.
  const seen = new Set<string>()
  const docSources = sources.filter((s) => {
    if (typeof s !== 'object' || s === null || !s.filename) return false
    const key = `${s.filename}#${s.page_number}`
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })
  if (docSources.length === 0) return null
  return (
    <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2">
      <span className="text-2xs font-medium uppercase tracking-wide text-slate-400 w-full">
        Sources
      </span>
      {docSources.map((s, i) => (
        <button
          key={i}
          type="button"
          onClick={(e) => {
            e.preventDefault()
            e.stopPropagation()
            onCitationClick(s.filename, s.page_number)
          }}
          className="inline-flex items-center gap-1.5 text-xs rounded-md border border-brand/20 bg-brand/5 text-brand hover:bg-brand/10 px-2.5 py-1 transition-colors"
        >
          <span className="max-w-[140px] truncate font-medium">{s.filename}</span>
          <span className="text-brand/60">p.{s.page_number}</span>
        </button>
      ))}
    </div>
  )
}

function TypingDots() {
  return (
    <span className="inline-flex items-end gap-0.5 h-4">
      {[0, 1, 2].map((i) => (
        <span
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-bounce"
          style={{ animationDelay: `${i * 0.15}s` }}
        />
      ))}
    </span>
  )
}

interface MessageBubbleProps {
  message: ChatMessage
  caseId: string
  onCitationClick: (filename: string, page: number) => void
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      type="button"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
          setTimeout(() => setCopied(false), 1500)
        } catch {
          // clipboard blocked (e.g. insecure context) — nothing to do
        }
      }}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700"
      aria-label={copied ? 'Copied' : 'Copy answer'}
    >
      {copied ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  )
}

/** Compact "which agents answered" line shown under finished answers. */
function AgentSummary({ steps }: { steps: AgentTraceStep[] }) {
  const agents = steps.filter((s) => s.agent !== 'orchestrator')
  if (agents.length === 0) return null
  return (
    <span className="inline-flex items-center gap-2">
      {agents.map((s) => {
        const { label, Icon, color } = getAgentMeta(s.agent)
        return (
          <span
            key={s.agent}
            className={cn('inline-flex items-center gap-1', s.status === 'error' && 'text-red-600')}
            title={s.status === 'error' ? `${label} failed` : label}
          >
            <Icon className={cn('h-3 w-3', s.status === 'error' ? 'text-red-500' : color)} />
            {label}
          </span>
        )
      })}
    </span>
  )
}

export default function MessageBubble({ message, caseId, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === 'user'
  const time = formatMessageTime(message.createdAt)

  if (isUser) {
    return (
      <div className="flex flex-col items-end gap-1">
        <div className="max-w-[80%] rounded-2xl rounded-br-md bg-brand px-4 py-2.5 text-sm text-white shadow-sm">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
        {time && <span className="pr-1 text-2xs text-slate-400">{time}</span>}
      </div>
    )
  }

  const components: Components = {
    a({ href, children }) {
      const cite = href ? parseCiteHref(href) : null
      if (cite) {
        return (
          <button
            type="button"
            onClick={(e) => {
              e.preventDefault()
              onCitationClick(cite.filename, cite.page)
            }}
            className="inline text-brand hover:text-brand-hover hover:underline font-medium cursor-pointer"
          >
            {children}
          </button>
        )
      }
      return (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {children}
        </a>
      )
    },
  }

  const finished = !message.isStreaming && message.content !== ''

  return (
    <div className="group flex gap-3">
      <div className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand-soft">
        <Scale className="h-4 w-4 text-brand" />
      </div>

      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-md border border-slate-200/80 bg-white px-4 py-3 shadow-sm">
          {message.isStreaming && message.content === '' ? (
            <TypingDots />
          ) : (
            <>
              <div className="prose prose-sm prose-slate max-w-none prose-headings:text-brand prose-headings:mt-3 prose-headings:mb-1.5 prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5 prose-hr:my-3 prose-table:text-xs">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                  {linkCitations(message.content)}
                </ReactMarkdown>
                {message.isStreaming && <TypingDots />}
              </div>

              {message.actions?.map((action, i) => (
                <ActionCard key={i} action={action} caseId={caseId} />
              ))}

              {message.sources && message.sources.length > 0 && (
                <SourcePills sources={message.sources} onCitationClick={onCitationClick} />
              )}
            </>
          )}
        </div>

        {finished && (
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 pl-1 text-2xs text-slate-400">
            {time && <span>{time}</span>}
            {message.agentTrace && <AgentSummary steps={message.agentTrace} />}
            <span className="ml-auto opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
              <CopyButton text={message.content} />
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
