import { useState } from 'react'
import { ArrowUpRight, ChevronDown, ChevronUp, Sparkles } from 'lucide-react'
import { readFlag, writeFlag } from '@/lib/storage'

const STORAGE_KEY = 'lexmind.suggestions.collapsed'

interface SuggestedQuestionsProps {
  questions: string[]
  loading?: boolean
  onSelect: (question: string) => void
  disabled?: boolean
}

/**
 * Empty-chat starter: a 2×2 grid of large, clickable question cards.
 */
export function SuggestedQuestionCards({ questions, loading, onSelect, disabled }: SuggestedQuestionsProps) {
  if (loading) {
    return (
      <div className="grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-2" aria-label="Loading suggestions">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-[60px] animate-pulse rounded-xl border border-slate-200 bg-white" />
        ))}
      </div>
    )
  }
  if (questions.length === 0) return null

  return (
    <div className="grid w-full max-w-2xl grid-cols-1 gap-2.5 sm:grid-cols-2">
      {questions.map((q) => (
        <button
          key={q}
          type="button"
          disabled={disabled}
          onClick={() => onSelect(q)}
          className="group flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 text-left text-sm text-slate-700 shadow-sm transition-all hover:-translate-y-px hover:border-brand/30 hover:shadow-md disabled:pointer-events-none disabled:opacity-50"
        >
          <span>{q}</span>
          <ArrowUpRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-300 transition-colors group-hover:text-brand" />
        </button>
      ))}
    </div>
  )
}

/**
 * During a conversation: one slim, horizontally scrolling row of chips that
 * can be minimised (remembered across visits).
 */
export default function SuggestedQuestions({ questions, onSelect, disabled }: SuggestedQuestionsProps) {
  const [collapsed, setCollapsed] = useState(() => readFlag(STORAGE_KEY, false))
  if (questions.length === 0) return null

  function toggle() {
    setCollapsed((value) => {
      writeFlag(STORAGE_KEY, !value)
      return !value
    })
  }

  return (
    <div className="shrink-0 border-t border-slate-200/70 bg-slate-50/80 px-4 pt-2 pb-1">
      <div className="mx-auto max-w-3xl">
      <button
        type="button"
        onClick={toggle}
        aria-expanded={!collapsed}
        className="flex items-center gap-1.5 rounded-md px-1 py-0.5 text-2xs font-semibold uppercase tracking-wider text-slate-400 hover:text-slate-600"
      >
        <Sparkles className="h-3 w-3" />
        Suggested questions
        <span className="font-normal normal-case tracking-normal">({questions.length})</span>
        {collapsed ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
      </button>

      {!collapsed && (
        <div className="flex gap-2 overflow-x-auto pt-1.5 pb-1.5 [scrollbar-width:thin]">
          {questions.map((q) => (
            <button
              key={q}
              type="button"
              title={q}
              disabled={disabled}
              onClick={() => onSelect(q)}
              className="max-w-[20rem] shrink-0 truncate rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 shadow-sm transition-colors hover:border-brand/30 hover:bg-brand/5 hover:text-brand disabled:cursor-not-allowed disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
      )}
      </div>
    </div>
  )
}
