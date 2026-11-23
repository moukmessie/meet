import { DisconnectReason } from 'livekit-client'

// Fork patch: when the instance is configured with a portal address
// (`portal_url` from /config/), Meet is only the room. Everything that leaves
// the room goes to that portal. The target is built from the configuration
// only and never from the current URL, so it cannot be steered by a link.

/**
 * Returns the origin of the portal, or null when it is not set or invalid.
 * Only http(s) addresses are accepted. A trailing path, query or hash is
 * dropped: the destinations below are fixed paths on the portal origin.
 */
export const normalizePortalUrl = (
  value: string | null | undefined
): string | null => {
  if (!value || typeof value !== 'string') return null
  try {
    const url = new URL(value.trim())
    if (url.protocol !== 'https:' && url.protocol !== 'http:') return null
    // credentials in the address are a spoofing trick (https://portal@evil.com)
    if (url.username || url.password) return null
    return url.origin
  } catch {
    return null
  }
}

/**
 * Where to go when leaving the room: the portal home for a member, the portal
 * feedback page for an anonymous guest.
 */
export const getPortalExitUrl = (
  portalUrl: string | null | undefined,
  isLoggedIn: boolean
): string | null => {
  const origin = normalizePortalUrl(portalUrl)
  if (!origin) return null
  return `${origin}${isLoggedIn ? '/' : '/feedback'}`
}

/** The portal home, used by the header logo and the hidden Meet screens. */
export const getPortalHomeUrl = (
  portalUrl: string | null | undefined
): string | null => {
  const origin = normalizePortalUrl(portalUrl)
  return origin ? `${origin}/` : null
}

/**
 * Disconnections that end the meeting for this participant: leaving, being
 * removed, a duplicate session and a room closed by the server (meeting
 * ended, limit reached). Network failures are left to the usual reconnection.
 */
export const isPortalExitReason = (reason: DisconnectReason | undefined) =>
  reason === DisconnectReason.CLIENT_INITIATED ||
  reason === DisconnectReason.DUPLICATE_IDENTITY ||
  reason === DisconnectReason.PARTICIPANT_REMOVED ||
  reason === DisconnectReason.ROOM_DELETED
