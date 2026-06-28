import { MessageSquareText } from 'lucide-react'

const SUGGESTED_QUESTIONS = [
  'Summarize this case and identify the key parties involved.',
  'What are the main facts and evidence in the uploaded documents?',
  'What legal risks or weaknesses should I be aware of?',
  'List all important dates and deadlines mentioned in the case files.',
  'What are the open issues that still need to be resolved?',
  'What arguments support our client\'s position?',
  'Are there any procedural gaps or missing documentation?',
  'What obligations or liabilities are described in the contracts?',
]

interface SuggestedQuestionsProps {
  onSelect: (question: string) => void
  disabled?: boolean
}

export default function SuggestedQuestions({ onSelect, disabled }: SuggestedQuestionsProps) {
  return (
    <div className="px-5 pb-3">
      <div className="flex items-center gap-2 mb-2.5">
        <MessageSquareText className="h-3.5 w-3.5 text-slate-400" />
        <p className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
          Suggested questions
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        {SUGGESTED_QUESTIONS.map((q) => (
          <button
            key={q}
            type="button"
            disabled={disabled}
            onClick={() => onSelect(q)}
            className="text-left text-xs rounded-lg border border-slate-200 bg-white px-3 py-2 text-slate-600 hover:border-[#1F3D6E]/30 hover:bg-[#1F3D6E]/5 hover:text-[#1F3D6E] transition-colors disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  )
}
