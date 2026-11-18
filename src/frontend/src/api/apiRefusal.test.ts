import { describe, expect, it } from 'vitest'
import { ApiError } from './ApiError'
import en from '../locales/en/rooms.json'
import fr from '../locales/fr/rooms.json'
import de from '../locales/de/rooms.json'
import es from '../locales/es/rooms.json'
import nl from '../locales/nl/rooms.json'
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

// Every code the backend can emit: the platform reasons forwarded by the room
// creation check and by the room limits, plus the backend's own codes.
const BACKEND_CODES = [
  'monthly_minutes_exhausted',
  'concurrent_rooms_limit',
  'concurrent_limit',
  'unknown_organization',
  'tenant_suspended',
  'tenant_closed',
  'no_active_subscription',
  'no_organization',
  'check_unavailable',
  'room_creation_refused',
  'entry_refused',
  'refused',
]

describe('refusal translations', () => {
  const locales = { en, fr, de, es, nl }

  it.each(Object.entries(locales))(
    'translates every backend code in %s',
    (_language, locale) => {
      const messages = locale.error.refusal as Record<string, string>
      for (const code of BACKEND_CODES) {
        expect(messages[code], code).toBeTruthy()
      }
      expect(messages.title).toBeTruthy()
      expect(messages.generic).toBeTruthy()
      expect(messages.monthly_minutes_exhausted).toContain('{{date}}')
    }
  )

  it('always prefers the translation of a known code to the detail', () => {
    for (const code of BACKEND_CODES) {
      const message = getRefusalMessage(
        { code, detail: 'Détail serveur' },
        t,
        'en'
      )
      expect(message).not.toBe('Détail serveur')
      expect(message).toContain('error.refusal.')
    }
  })

  it('uses the detail only for an unknown code', () => {
    expect(
      getRefusalMessage(
        { code: 'brand_new', detail: 'Détail serveur' },
        t,
        'en'
      )
    ).toBe('Détail serveur')
  })

  it('extracts the refusal of a 403 without detail', () => {
    const error = new ApiError(403, {
      code: 'tenant_suspended',
      quota: { resets_at: '2026-12-01T00:00:00Z' },
    })
    expect(getApiRefusal(error)?.code).toBe('tenant_suspended')
  })

  it('does not treat a deleted room (410) or a server error as a refusal', () => {
    expect(getApiRefusal(new ApiError(410, { code: 'x' }))).toBeUndefined()
    expect(getApiRefusal(new ApiError(500, { code: 'x' }))).toBeUndefined()
  })
})
