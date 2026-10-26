import type { CalendarAction } from './types'

function parseDate(value: string | null): Date | null {
  if (!value) return null
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? null : d
}

/** Date → "20261103T100000" (floating local time, as the user typed it). */
function icsDate(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
    `T${pad(d.getHours())}${pad(d.getMinutes())}00`
  )
}

/** Escape text per RFC 5545 (backslash, semicolon, comma, newline). */
function icsText(value: string) {
  return value
    .replace(/\\/g, '\\\\')
    .replace(/;/g, '\\;')
    .replace(/,/g, '\\,')
    .replace(/\r?\n/g, '\\n')
}

/**
 * Build an iCalendar file for a drafted event, or null if it has no usable
 * start date. The end defaults to one hour after the start.
 */
export function buildIcs(event: CalendarAction, uid: string = crypto.randomUUID()): string | null {
  const startDate = parseDate(event.start)
  if (!startDate) return null
  const endDate = parseDate(event.end) ?? new Date(startDate.getTime() + 60 * 60_000)
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '')
  const description = [
    event.description,
    event.attendees.length ? `Attendees: ${event.attendees.join(', ')}` : '',
  ]
    .filter(Boolean)
    .join('\n\n')

  return [
    'BEGIN:VCALENDAR',
    'VERSION:2.0',
    'PRODID:-//LexMind AI//EN',
    'BEGIN:VEVENT',
    `UID:${uid}@lexmind`,
    `DTSTAMP:${stamp}`,
    `DTSTART:${icsDate(startDate)}`,
    `DTEND:${icsDate(endDate)}`,
    `SUMMARY:${icsText(event.title)}`,
    event.location ? `LOCATION:${icsText(event.location)}` : '',
    description ? `DESCRIPTION:${icsText(description)}` : '',
    'END:VEVENT',
    'END:VCALENDAR',
  ]
    .filter(Boolean)
    .join('\r\n')
}
