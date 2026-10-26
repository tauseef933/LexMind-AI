import { describe, expect, it } from 'vitest'
import { buildIcs } from './ics'
import type { CalendarAction } from './types'

const event: CalendarAction = {
  action_type: 'calendar',
  title: 'Hearing prep; Smith, Jones',
  start: '2026-11-03T10:00',
  end: null,
  location: 'Room 4',
  attendees: ['Alice', 'Bob'],
  description: 'Line one\nLine two',
}

describe('buildIcs', () => {
  it('builds a valid VEVENT with a one-hour default duration', () => {
    const ics = buildIcs(event, 'fixed-uid')!
    const lines = ics.split('\r\n')

    expect(lines[0]).toBe('BEGIN:VCALENDAR')
    expect(lines[lines.length - 1]).toBe('END:VCALENDAR')
    expect(lines).toContain('UID:fixed-uid@lexmind')
    expect(lines).toContain('DTSTART:20261103T100000')
    expect(lines).toContain('DTEND:20261103T110000')
    expect(lines).toContain('LOCATION:Room 4')
  })

  it('escapes special characters per RFC 5545', () => {
    const ics = buildIcs(event, 'x')!
    expect(ics).toContain('SUMMARY:Hearing prep\\; Smith\\, Jones')
    expect(ics).toContain('DESCRIPTION:Line one\\nLine two\\n\\nAttendees: Alice\\, Bob')
  })

  it('uses an explicit end time when given', () => {
    const ics = buildIcs({ ...event, end: '2026-11-03T12:30' }, 'x')!
    expect(ics).toContain('DTEND:20261103T123000')
  })

  it('returns null without a usable start date', () => {
    expect(buildIcs({ ...event, start: null })).toBeNull()
    expect(buildIcs({ ...event, start: 'next tuesday-ish' })).toBeNull()
  })

  it('omits empty optional fields', () => {
    const ics = buildIcs({ ...event, location: '', description: '', attendees: [] }, 'x')!
    expect(ics).not.toContain('LOCATION:')
    expect(ics).not.toContain('DESCRIPTION:')
  })
})
