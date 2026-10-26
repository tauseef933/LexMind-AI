import { describe, expect, it } from 'vitest'
import { cn, formatMessageTime, normalizeFilename, parseTimestamp } from './utils'

describe('cn', () => {
  it('keeps the custom text-2xs size next to a text colour', () => {
    expect(cn('text-2xs', 'text-red-600')).toBe('text-2xs text-red-600')
  })

  it('still lets a later size override text-2xs', () => {
    expect(cn('text-2xs', 'text-sm')).toBe('text-sm')
  })
})

describe('normalizeFilename', () => {
  it('matches cited names that use typographic hyphens or spaces', () => {
    expect(normalizeFilename('Northwind\u2011Harbor\u2011MSA.pdf')).toBe(normalizeFilename('Northwind-Harbor-MSA.pdf'))
    expect(normalizeFilename('My\u00a0NDA.PDF ')).toBe('my nda.pdf')
  })
})

describe('timestamps', () => {
  it('treats zone-less API timestamps as UTC', () => {
    expect(parseTimestamp('2026-10-26T10:00:00').toISOString()).toBe('2026-10-26T10:00:00.000Z')
    expect(parseTimestamp('2026-10-26T10:00:00Z').toISOString()).toBe('2026-10-26T10:00:00.000Z')
  })

  it('shows only the time for today and adds the date otherwise', () => {
    const now = new Date('2026-10-26T15:00:00Z')
    const today = formatMessageTime('2026-10-26T14:05:00Z', now)
    const earlier = formatMessageTime('2026-10-20T14:05:00Z', now)
    expect(today).not.toMatch(/Oct/)
    expect(earlier).toMatch(/Oct/)
    expect(formatMessageTime(undefined)).toBe('')
    expect(formatMessageTime('not a date')).toBe('')
  })
})
