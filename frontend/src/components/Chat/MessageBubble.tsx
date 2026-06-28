import { cn } from '@/lib/utils'
import type { ChatMessage, Source } from '@/lib/types'

const CITATION_RE = /\[Source:\s*([^,\]]+),\s*Page\s*(\d+)\]/g

interface ParsedSegment {
  type: 'text' | 'citation'
  value: string
  filename?: string
  page?: number
}

function parseContent(content: string): ParsedSegment[] {
  const segments: ParsedSegment[] = []
  let last = 0

  for (const match of content.matchAll(CITATION_RE)) {
    const start = match.index ?? 0
    if (start > last) {
      segments.push({ type: 'text', value: content.slice(last, start) })
    }
    segments.push({
      type: 'citation',
      value: match[0],
      filename: match[1].trim(),
      page: parseInt(match[2], 10),
    })
    last = start + match[0].length
  }
  if (last < content.length) {
    segments.push({ type: 'text', value: content.slice(last) })
  }
  return segments
}

function SourcePills({
  sources,
  onCitationClick,
}: {
  sources: Source[]
  onCitationClick: (filename: string, page: number) => void
}) {
  if (sources.length === 0) return null
  return (
    <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap gap-2">
      <span className="text-[11px] font-medium uppercase tracking-wide text-slate-400 w-full">
        Sources
      </span>
      {sources.map((s, i) => (
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
  onCitationClick: (filename: string, page: number) => void
}

export default function MessageBubble({ message, onCitationClick }: MessageBubbleProps) {
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

  const segments = parseContent(message.content)

  return (
    <div className="flex justify-start px-5">
      <div className="max-w-[82%] rounded-2xl rounded-tl-md bg-white border border-slate-200/80 px-4 py-3 shadow-sm">
        {message.isStreaming && message.content === '' ? (
          <TypingDots />
        ) : (
          <>
            <div className="text-sm text-slate-800 leading-relaxed">
              {segments.map((seg, i) => {
                if (seg.type === 'citation') {
                  return (
                    <button
                      key={i}
                      type="button"
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        onCitationClick(seg.filename!, seg.page!)
                      }}
                      className="inline text-[#1F3D6E] hover:text-[#163056] hover:underline font-medium cursor-pointer"
                    >
                      {seg.value}
                    </button>
                  )
                }
                return (
                  <span key={i} className="whitespace-pre-wrap">
                    {seg.value}
                  </span>
                )
              })}
              {message.isStreaming && <TypingDots />}
            </div>

            {message.sources && message.sources.length > 0 && (
              <SourcePills sources={message.sources} onCitationClick={onCitationClick} />
            )}
          </>
        )}
      </div>
    </div>
  )
}
