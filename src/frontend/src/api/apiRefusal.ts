import { ApiError } from './ApiError'

export type ApiRefusalQuota = {
  resets_at?: string
  [key: string]: unknown
}

export type ApiRefusal = {
  detail?: string
  code?: string
  quota?: ApiRefusalQuota
}

const KNOWN_CODES = [
  'monthly_minutes_exhausted',
  'concurrent_limit',
  'concurrent_rooms_limit',
  'no_organization',
  'unknown_organization',
  'tenant_suspended',
  'tenant_closed',
  'no_active_subscription',
  'entry_refused',
  'check_unavailable',
  'room_creation_refused',
  'refused',
  'scheduled_meeting_not_started',
  'scheduled_meeting_not_opened',
  'scheduled_meeting_canceled',
  'scheduled_meeting_ended',
  'scheduling_not_available',
] as const

const REFUSAL_TIME_ZONE = 'Europe/Paris'

const asString = (value: unknown): string | undefined =>
  typeof value === 'string' && value.length > 0 ? value : undefined

/**
 * Extract the refusal payload ({detail, code, quota}) of an HTTP 403 API error.
 * Returns undefined for any other error.
 */
export const getApiRefusal = (error: unknown): ApiRefusal | undefined => {
  if (!(error instanceof ApiError) || error.statusCode !== 403) return
  const body = error.body
  if (!body || typeof body !== 'object') return {}
  const { detail, code, quota } = body as Record<string, unknown>
  return {
    detail: asString(detail),
    code: asString(code),
    quota:
      quota && typeof quota === 'object'
        ? (quota as ApiRefusalQuota)
        : undefined,
  }
}

/** Format an ISO 8601 date in the Europe/Paris time zone, undefined if invalid. */
export const formatResetDate = (
  isoDate: unknown,
  language: string
): string | undefined => {
  if (typeof isoDate !== 'string') return
  const date = new Date(isoDate)
  if (Number.isNaN(date.getTime())) return
  try {
    return new Intl.DateTimeFormat(language, {
      dateStyle: 'long',
      timeStyle: 'short',
      timeZone: REFUSAL_TIME_ZONE,
    }).format(date)
  } catch {
    return
  }
}

type Translate = (key: string, options?: Record<string, unknown>) => string

/**
 * Build the user-facing message of a refusal. The translated message of a known
 * code is always preferred to the server `detail` (which is not translated);
 * `detail` is only the fallback for an unknown code, then a generic message.
 */
export const getRefusalMessage = (
  refusal: ApiRefusal,
  t: Translate,
  language: string
): string => {
  const code = KNOWN_CODES.find((known) => known === refusal.code)
  if (code === 'monthly_minutes_exhausted') {
    const date = formatResetDate(refusal.quota?.resets_at, language)
    return date
      ? t('error.refusal.monthly_minutes_exhausted', { date })
      : t('error.refusal.monthly_minutes_exhausted_noDate')
  }
  if (code) return t(`error.refusal.${code}`)
  return refusal.detail ?? t('error.refusal.generic')
}
