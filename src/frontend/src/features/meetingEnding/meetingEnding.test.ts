import { describe, expect, it } from 'vitest'
import { decodeMeetingEnding, getCountdown } from './meetingEnding'

const encode = (value: unknown) =>
  new TextEncoder().encode(
    typeof value === 'string' ? value : JSON.stringify(value)
  )

const NOW = Date.parse('2026-11-17T10:00:00Z')
const notification = (data: unknown, type = 'meetingEnding') =>
  encode({ type, data })

describe('decodeMeetingEnding', () => {
  it('computes endsAt from the reception time', () => {
    expect(
      decodeMeetingEnding(
        notification({ seconds_left: 240, reason: 'duration_limit' }),
        NOW
      )
    ).toEqual({ endsAt: NOW + 240_000, reason: 'duration_limit' })
  })

  it.each(['monthly_limit', 'concurrent_limit'])('accepts %s', (reason) => {
    expect(
      decodeMeetingEnding(notification({ seconds_left: 0, reason }), NOW)
    ).toMatchObject({ reason, endsAt: NOW })
  })

  it('ignores other notification types', () => {
    expect(
      decodeMeetingEnding(notification({ emoji: 'x' }, 'reactionReceived'), NOW)
    ).toBeUndefined()
  })

  it('rejects malformed payloads', () => {
    const reason = 'duration_limit'
    for (const payload of [
      encode('not json'),
      encode(null),
      encode({ type: 'meetingEnding' }),
      notification({ reason }),
      notification({ seconds_left: -1, reason }),
      notification({ seconds_left: 1.5, reason }),
      notification({ seconds_left: '60', reason }),
      notification({ seconds_left: 999_999, reason }),
      notification({ seconds_left: 60, reason: 'x' }),
    ]) {
      expect(decodeMeetingEnding(payload, NOW)).toBeUndefined()
    }
  })
})

describe('getCountdown', () => {
  const endsAt = Date.parse('2026-11-17T10:00:00Z')

  it('rounds the remaining minutes up', () => {
    expect(getCountdown(endsAt, endsAt - 4 * 60_000)).toEqual({
      kind: 'minutes',
      minutes: 4,
    })
    expect(getCountdown(endsAt, endsAt - 3 * 60_000 - 1000)).toEqual({
      kind: 'minutes',
      minutes: 4,
    })
  })

  it('reports less than a minute then the end', () => {
    expect(getCountdown(endsAt, endsAt - 59_000)).toEqual({
      kind: 'lessThanMinute',
    })
    expect(getCountdown(endsAt, endsAt)).toEqual({ kind: 'ended' })
    expect(getCountdown(endsAt, endsAt + 5000)).toEqual({ kind: 'ended' })
  })
})
