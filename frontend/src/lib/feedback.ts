import { createContext, useContext } from 'react'

export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastOptions {
  title: string
  description?: string
  variant?: ToastVariant
}

export interface ConfirmOptions {
  title: string
  message?: string
  confirmLabel?: string
  cancelLabel?: string
  destructive?: boolean
}

export interface FeedbackApi {
  toast: (options: ToastOptions) => void
  /** Resolves true when the user confirms, false when they cancel. */
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

export const FeedbackContext = createContext<FeedbackApi | null>(null)

function useFeedback(): FeedbackApi {
  const api = useContext(FeedbackContext)
  if (!api) throw new Error('useToast/useConfirm must be used inside <FeedbackProvider>')
  return api
}

export const useToast = () => useFeedback().toast
export const useConfirm = () => useFeedback().confirm
