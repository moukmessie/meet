import { describe, expect, it } from 'vitest'
import { decodeMeetingEnding, getCountdown } from './meetingEnding'

const encode = (value: unknown) =>
  new TextEncoder().encode(
    typeof value === 'string' ? value : JSON.stringify(value)
  )

describe('decodeMeetingEnding', () => {
  it('decodes a valid payload', () => {
    expect(
      decodeMeetingEnding(
        encode({ endsAt: '2026-11-17T10:00:00Z', reason: 'duration_limit' })
      )
    ).toEqual({
      endsAt: Date.parse('2026-11-17T10:00:00Z'),
      reason: 'duration_limit',
    })
  })

  it.each(['monthly_limit', 'concurrent_limit'])('accepts %s', (reason) => {
    expect(
      decodeMeetingEnding(encode({ endsAt: '2026-11-17T10:00:00Z', reason }))
    ).toMatchObject({ reason })
  })

  it('rejects malformed payloads', () => {
    expect(decodeMeetingEnding(encode('not json'))).toBeUndefined()
    expect(decodeMeetingEnding(encode(null))).toBeUndefined()
    expect(
      decodeMeetingEnding(encode({ reason: 'duration_limit' }))
    ).toBeUndefined()
    expect(
      decodeMeetingEnding(
        encode({ endsAt: 'garbage', reason: 'duration_limit' })
      )
    ).toBeUndefined()
    expect(
      decodeMeetingEnding(
        encode({ endsAt: '2026-11-17T10:00:00Z', reason: 'x' })
      )
    ).toBeUndefined()
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
