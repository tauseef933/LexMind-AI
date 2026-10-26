import { fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SuggestedQuestions, { SuggestedQuestionCards } from './SuggestedQuestions'

const QUESTIONS = ['What is the liability cap?', 'Which law governs the NDA?']

beforeEach(() => localStorage.clear())

describe('SuggestedQuestionCards', () => {
  it('sends the question when a card is clicked', () => {
    const onSelect = vi.fn()
    render(<SuggestedQuestionCards questions={QUESTIONS} onSelect={onSelect} />)
    fireEvent.click(screen.getByRole('button', { name: /liability cap/ }))
    expect(onSelect).toHaveBeenCalledWith('What is the liability cap?')
  })

  it('shows placeholders while loading', () => {
    render(<SuggestedQuestionCards questions={[]} loading onSelect={() => {}} />)
    expect(screen.getByLabelText('Loading suggestions')).toBeInTheDocument()
  })
})

describe('SuggestedQuestions bar', () => {
  it('can be minimised, and remembers it', () => {
    const { unmount } = render(<SuggestedQuestions questions={QUESTIONS} onSelect={() => {}} />)
    const toggle = screen.getByRole('button', { name: /suggested questions/i })

    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('button', { name: QUESTIONS[0] })).toBeInTheDocument()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('button', { name: QUESTIONS[0] })).not.toBeInTheDocument()

    unmount()
    render(<SuggestedQuestions questions={QUESTIONS} onSelect={() => {}} />)
    expect(screen.getByRole('button', { name: /suggested questions/i })).toHaveAttribute('aria-expanded', 'false')
  })

  it('renders nothing when there are no questions left', () => {
    const { container } = render(<SuggestedQuestions questions={[]} onSelect={() => {}} />)
    expect(container).toBeEmptyDOMElement()
  })
})
