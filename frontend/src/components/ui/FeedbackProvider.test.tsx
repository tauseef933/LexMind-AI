import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import FeedbackProvider from './FeedbackProvider'
import { useConfirm, useToast } from '@/lib/feedback'

function Harness({ onResult }: { onResult: (ok: boolean) => void }) {
  const toast = useToast()
  const confirm = useConfirm()
  return (
    <>
      <button onClick={() => toast({ title: 'Saved', description: 'All good', variant: 'success' })}>toast</button>
      <button
        onClick={async () =>
          onResult(await confirm({ title: 'Delete "NDA"?', confirmLabel: 'Delete case', destructive: true }))
        }
      >
        ask
      </button>
    </>
  )
}

function setup() {
  const onResult = vi.fn()
  render(
    <FeedbackProvider>
      <Harness onResult={onResult} />
    </FeedbackProvider>,
  )
  return onResult
}

afterEach(() => vi.useRealTimers())

describe('FeedbackProvider', () => {
  it('shows a toast that disappears on its own', () => {
    vi.useFakeTimers()
    setup()
    fireEvent.click(screen.getByText('toast'))
    expect(screen.getByRole('status')).toHaveTextContent('SavedAll good')

    act(() => vi.advanceTimersByTime(4100))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('toasts can be dismissed', () => {
    setup()
    fireEvent.click(screen.getByText('toast'))
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('confirm resolves true when confirmed', async () => {
    const onResult = setup()
    fireEvent.click(screen.getByText('ask'))
    expect(screen.getByRole('alertdialog')).toHaveTextContent('Delete "NDA"?')
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Delete case' })))
    expect(onResult).toHaveBeenCalledWith(true)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })

  it('confirm resolves false on cancel and on Escape', async () => {
    const onResult = setup()
    fireEvent.click(screen.getByText('ask'))
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Cancel' })))
    expect(onResult).toHaveBeenLastCalledWith(false)

    fireEvent.click(screen.getByText('ask'))
    await act(async () => fireEvent.keyDown(window, { key: 'Escape' }))
    expect(onResult).toHaveBeenLastCalledWith(false)
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  })
})
