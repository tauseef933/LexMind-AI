import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { ChatMessage, Source } from '@/lib/types'
import ActionCard from './ActionCard'

const CITATION_RE = /\[Source:\s*([^,\]]+),\s*Page\s*(\d+)\]/g
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
  const docSources = sources.filter((s) => typeof s === 'object' && s !== null && s.filename)
  if (docSources.length === 0) return null
  return (
    <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400 w-full">
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
          className="inline-flex items-center gap-1.5 text-xs rounded-md border border-[#1F3D6E]/20 bg-[#1F3D6E]/5 text-[#1F3D6E] hover:bg-[#1F3D6E]/10 px-2.5 py-1 transition-colors"
        >
          <span className="max-w-[140px] truncate font-medium">{s.filename}</span>
          <span className="text-[#1F3D6E]/60">p.{s.page_number}</span>
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

export default function MessageBubble({ message, caseId, onCitationClick }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end px-5">
        <div className="max-w-[75%] rounded-2xl rounded-tr-md px-4 py-3 text-sm text-white shadow-md bg-[#1F3D6E]">
          <p className="whitespace-pre-wrap leading-relaxed">{message.content}</p>
        </div>
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
            className="inline text-[#1F3D6E] hover:text-[#163056] hover:underline font-medium cursor-pointer"
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

  return (
    <div className="flex justify-start px-5">
      <div className="max-w-[82%] rounded-2xl rounded-tl-md bg-white border border-slate-200/80 px-4 py-3 shadow-sm">
        {message.isStreaming && message.content === '' ? (
          <TypingDots />
        ) : (
          <>
            <div className="prose prose-sm prose-slate max-w-none prose-headings:text-[#1F3D6E] prose-headings:mt-3 prose-headings:mb-1.5 prose-p:my-1.5 prose-ul:my-1.5 prose-li:my-0.5 prose-hr:my-3">
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
    </div>
  )
}
