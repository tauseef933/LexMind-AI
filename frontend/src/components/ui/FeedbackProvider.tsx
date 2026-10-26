import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { cn } from '@/lib/utils'
import {
  FeedbackContext,
  type ConfirmOptions,
  type FeedbackApi,
  type ToastOptions,
  type ToastVariant,
} from '@/lib/feedback'

const TOAST_MS = 4000

interface Toast extends ToastOptions {
  id: number
}

interface PendingConfirm extends ConfirmOptions {
  resolve: (ok: boolean) => void
}

const TOAST_STYLE: Record<ToastVariant, { Icon: typeof Info; className: string }> = {
  success: { Icon: CheckCircle2, className: 'text-emerald-600' },
  error: { Icon: XCircle, className: 'text-red-600' },
  info: { Icon: Info, className: 'text-brand' },
}

function ConfirmDialog({ pending, onClose }: { pending: PendingConfirm; onClose: (ok: boolean) => void }) {
  const confirmRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    confirmRef.current?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
      onMouseDown={(e) => e.target === e.currentTarget && onClose(false)}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-5 shadow-2xl"
      >
        <div className="flex gap-3">
          {pending.destructive && (
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-red-50">
              <AlertTriangle className="h-4 w-4 text-red-600" />
            </div>
          )}
          <div className="min-w-0">
            <h2 id="confirm-title" className="text-sm font-semibold text-slate-900">
              {pending.title}
            </h2>
            {pending.message && <p className="mt-1 text-sm text-slate-500">{pending.message}</p>}
          </div>
        </div>
        <div className="mt-5 flex justify-end gap-2">
          <button
            type="button"
            onClick={() => onClose(false)}
            className="rounded-lg border border-slate-200 px-3.5 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50"
          >
            {pending.cancelLabel ?? 'Cancel'}
          </button>
          <button
            ref={confirmRef}
            type="button"
            onClick={() => onClose(true)}
            className={cn(
              'rounded-lg px-3.5 py-2 text-sm font-medium text-white',
              pending.destructive ? 'bg-red-600 hover:bg-red-700' : 'bg-brand hover:bg-brand-hover',
            )}
          >
            {pending.confirmLabel ?? 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * Provides toast notifications and a promise-based confirm dialog to the app,
 * replacing window.alert / window.confirm.
 */
export default function FeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const [pending, setPending] = useState<PendingConfirm | null>(null)
  const nextId = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((all) => all.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (options: ToastOptions) => {
      const id = ++nextId.current
      setToasts((all) => [...all.slice(-2), { ...options, id }])   // keep at most 3
      setTimeout(() => dismiss(id), TOAST_MS)
    },
    [dismiss],
  )

  const confirm = useCallback(
    (options: ConfirmOptions) => new Promise<boolean>((resolve) => setPending({ ...options, resolve })),
    [],
  )

  const closeConfirm = useCallback(
    (ok: boolean) => {
      pending?.resolve(ok)
      setPending(null)
    },
    [pending],
  )

  const api = useMemo<FeedbackApi>(() => ({ toast, confirm }), [toast, confirm])

  return (
    <FeedbackContext.Provider value={api}>
      {children}

      <div aria-live="polite" className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-80 flex-col gap-2">
        {toasts.map((t) => {
          const { Icon, className } = TOAST_STYLE[t.variant ?? 'info']
          return (
            <div
              key={t.id}
              role="status"
              className="pointer-events-auto flex items-start gap-2.5 rounded-xl border border-slate-200 bg-white p-3 shadow-lg animate-in"
            >
              <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', className)} />
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-slate-900">{t.title}</p>
                {t.description && <p className="mt-0.5 text-xs text-slate-500">{t.description}</p>}
              </div>
              <button
                type="button"
                onClick={() => dismiss(t.id)}
                aria-label="Dismiss"
                className="rounded p-0.5 text-slate-400 hover:text-slate-600"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            </div>
          )
        })}
      </div>

      {pending && <ConfirmDialog pending={pending} onClose={closeConfirm} />}
    </FeedbackContext.Provider>
  )
}
