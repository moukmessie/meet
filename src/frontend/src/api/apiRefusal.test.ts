import { describe, expect, it } from 'vitest'
import { ApiError } from './ApiError'
import { formatResetDate, getApiRefusal, getRefusalMessage } from './apiRefusal'

const t = (key: string, options?: Record<string, unknown>) =>
  options?.date ? `${key}|${options.date}` : key

describe('getApiRefusal', () => {
  it('extracts detail, code and quota from a 403', () => {
    const error = new ApiError(403, {
      detail: 'Nope',
      code: 'monthly_minutes_exhausted',
      quota: { resets_at: '2026-12-01T00:00:00+01:00' },
    })
    expect(getApiRefusal(error)).toEqual({
      detail: 'Nope',
      code: 'monthly_minutes_exhausted',
      quota: { resets_at: '2026-12-01T00:00:00+01:00' },
    })
  })

  it('ignores other statuses and other errors', () => {
    expect(getApiRefusal(new ApiError(404, { detail: 'x' }))).toBeUndefined()
    expect(getApiRefusal(new Error('boom'))).toBeUndefined()
    expect(getApiRefusal(undefined)).toBeUndefined()
  })

  it('accepts a 403 without a usable body', () => {
    expect(getApiRefusal(new ApiError(403, undefined))).toEqual({})
  })
})

describe('formatResetDate', () => {
  it('formats in the Europe/Paris time zone', () => {
    // 23:30 UTC is already the next day, 00:30, in Paris (CET, winter)
    expect(formatResetDate('2026-11-30T23:30:00Z', 'fr')).toBe(
      '1 décembre 2026 à 00:30'
    )
  })

  it('returns undefined for invalid dates', () => {
    expect(formatResetDate('not a date', 'fr')).toBeUndefined()
    expect(formatResetDate(undefined, 'fr')).toBeUndefined()
  })
})

describe('getRefusalMessage', () => {
  it('uses the monthly quota message with the renewal date', () => {
    const message = getRefusalMessage(
      {
        code: 'monthly_minutes_exhausted',
        quota: { resets_at: '2026-11-30T23:30:00Z' },
      },
      t,
      'fr'
    )
    expect(message).toBe(
      'error.refusal.monthly_minutes_exhausted|1 décembre 2026 à 00:30'
    )
  })

  it('omits the date when resets_at is missing', () => {
    expect(
      getRefusalMessage({ code: 'monthly_minutes_exhausted' }, t, 'fr')
    ).toBe('error.refusal.monthly_minutes_exhausted_noDate')
  })

  it('translates the room creation refusal codes', () => {
    for (const code of [
      'no_organization',
      'check_unavailable',
      'room_creation_refused',
    ]) {
      expect(getRefusalMessage({ code }, t, 'fr')).toBe(`error.refusal.${code}`)
    }
  })

  it('falls back to the detail then to a generic message', () => {
    expect(
      getRefusalMessage({ code: 'other', detail: 'Server' }, t, 'fr')
    ).toBe('Server')
    expect(getRefusalMessage({}, t, 'fr')).toBe('error.refusal.generic')
  })
})
