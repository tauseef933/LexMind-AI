import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Teach tailwind-merge about the custom `text-2xs` size (tailwind.config.js),
// otherwise it is mistaken for a colour and dropped next to e.g. text-red-600.
const twMerge = extendTailwindMerge({
  extend: { classGroups: { 'font-size': [{ text: ['2xs'] }] } },
})

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

/**
 * Compare-friendly filename: models sometimes cite "Northwind\u2011NDA.pdf" with
 * typographic hyphens or no-break spaces instead of the real characters.
 */
export function normalizeFilename(name: string): string {
  return name
    .replace(/[\u2010-\u2015\u2212]/g, '-')
    .replace(/[\u00a0\u202f]/g, ' ')
    .trim()
    .toLowerCase()
}

/**
 * Parse an API timestamp. The backend stores UTC without a zone suffix
 * ("2026-10-26T10:00:00"), so treat zone-less values as UTC.
 */
export function parseTimestamp(value: string): Date {
  return new Date(/[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`)
}

/** "14:05" for today, otherwise "26 Oct, 14:05". */
export function formatMessageTime(value: string | undefined, now: Date = new Date()): string {
  if (!value) return ''
  const date = parseTimestamp(value)
  if (Number.isNaN(date.getTime())) return ''
  const time = date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === now.toDateString()) return time
  const day = date.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
  return `${day}, ${time}`
}
