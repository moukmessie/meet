export const MEETING_ENDING_TYPE = 'meetingEnding'

// Upper bound of a plausible notice (24 hours), to reject absurd values.
export const MAX_SECONDS_LEFT = 86_400

export const MEETING_ENDING_REASONS = [
  'duration_limit',
  'monthly_limit',
  'concurrent_limit',
] as const

export type MeetingEndingReason = (typeof MEETING_ENDING_REASONS)[number]

export type MeetingEnding = {
  endsAt: number // epoch milliseconds
  reason: MeetingEndingReason
}

/**
 * Decode a meetingEnding notification, sent by the platform as a data message
 * without topic, in the Meet notification format:
 * {"type": "meetingEnding", "data": {"seconds_left": <int>, "reason": "duration_limit" | ...}}.
 * The end instant is the reception time plus seconds_left. Returns undefined
 * for other notification types and malformed payloads.
 */
export const decodeMeetingEnding = (
  payload: Uint8Array,
  now: number = Date.now()
): MeetingEnding | undefined => {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder().decode(payload))
    if (!parsed || typeof parsed !== 'object') return
    const { type, data } = parsed as Record<string, unknown>
    if (type !== MEETING_ENDING_TYPE) return
    if (!data || typeof data !== 'object') return
    const { seconds_left: secondsLeft, reason } = data as Record<
      string,
      unknown
    >
    if (
      typeof secondsLeft !== 'number' ||
      !Number.isInteger(secondsLeft) ||
      secondsLeft < 0 ||
      secondsLeft > MAX_SECONDS_LEFT
    )
      return
    if (!MEETING_ENDING_REASONS.includes(reason as MeetingEndingReason)) return
    return {
      endsAt: now + secondsLeft * 1000,
      reason: reason as MeetingEndingReason,
    }
  } catch {
    return
  }
}

export type Countdown =
  | { kind: 'minutes'; minutes: number }
  | { kind: 'lessThanMinute' }
  | { kind: 'ended' }

/** Remaining time, with a one minute granularity to keep it screen reader friendly. */
export const getCountdown = (endsAt: number, now: number): Countdown => {
  const remaining = endsAt - now
  if (remaining <= 0) return { kind: 'ended' }
  if (remaining < 60_000) return { kind: 'lessThanMinute' }
  return { kind: 'minutes', minutes: Math.ceil(remaining / 60_000) }
}
