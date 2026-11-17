export const MEETING_ENDING_TOPIC = 'meetingEnding'

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
 * Decode a `meetingEnding` data message payload:
 * {"endsAt": "<ISO 8601>", "reason": "duration_limit" | ...}.
 * Returns undefined when the payload is malformed.
 */
export const decodeMeetingEnding = (
  payload: Uint8Array
): MeetingEnding | undefined => {
  try {
    const parsed: unknown = JSON.parse(new TextDecoder().decode(payload))
    if (!parsed || typeof parsed !== 'object') return
    const { endsAt, reason } = parsed as Record<string, unknown>
    if (typeof endsAt !== 'string') return
    const time = new Date(endsAt).getTime()
    if (Number.isNaN(time)) return
    if (!MEETING_ENDING_REASONS.includes(reason as MeetingEndingReason)) return
    return { endsAt: time, reason: reason as MeetingEndingReason }
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
