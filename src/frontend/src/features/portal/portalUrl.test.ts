import { afterEach, describe, expect, it, vi } from 'vitest'
import { DisconnectReason } from 'livekit-client'
import {
  getPortalExitUrl,
  isPortalExitReason,
  getPortalHomeUrl,
  normalizePortalUrl,
} from './portalUrl'

describe('normalizePortalUrl', () => {
  it('keeps upstream behaviour when empty', () => {
    expect(normalizePortalUrl(undefined)).toBeNull()
    expect(normalizePortalUrl(null)).toBeNull()
    expect(normalizePortalUrl('')).toBeNull()
    expect(normalizePortalUrl('   ')).toBeNull()
  })

  it('keeps only the origin of an http(s) address', () => {
    expect(normalizePortalUrl('https://portal.example.com')).toBe(
      'https://portal.example.com'
    )
    expect(normalizePortalUrl('https://portal.example.com/a/b?x=1#h')).toBe(
      'https://portal.example.com'
    )
    expect(normalizePortalUrl('http://localhost:8000/')).toBe(
      'http://localhost:8000'
    )
  })

  // negative: anything that is not a plain http(s) address is refused
  it.each([
    'javascript:alert(1)',
    'data:text/html,<script>1</script>',
    'ftp://portal.example.com',
    '//portal.example.com',
    '/feedback',
    'not a url',
    'https://portal@evil.example.com',
    'https://portal.example.com@evil.example.com/',
    'https://user:secret@portal.example.com',
    'https://:secret@portal.example.com',
  ])('rejects %s', (value) => {
    expect(normalizePortalUrl(value)).toBeNull()
  })
})

describe('getPortalExitUrl', () => {
  afterEach(() => vi.unstubAllGlobals())
  const portal = 'https://portal.example.com'

  it('sends a member to the portal home', () => {
    expect(getPortalExitUrl(portal, true)).toBe('https://portal.example.com/')
  })

  it('sends an anonymous guest to the portal feedback page', () => {
    expect(getPortalExitUrl(portal, false)).toBe(
      'https://portal.example.com/feedback'
    )
  })

  it('is null without portal, so the upstream flow applies', () => {
    expect(getPortalExitUrl(undefined, true)).toBeNull()
    expect(getPortalExitUrl('', false)).toBeNull()
  })

  it('does not depend on the current URL', () => {
    vi.stubGlobal('location', {
      href: 'https://meet.example.com/?next=https://evil.example.org',
      search: '?next=https://evil.example.org&returnTo=//evil.example.org',
    })
    expect(getPortalExitUrl(portal, true)).toBe('https://portal.example.com/')
    expect(getPortalExitUrl(portal, false)).toBe(
      'https://portal.example.com/feedback'
    )
    expect(getPortalHomeUrl(portal)).toBe('https://portal.example.com/')
  })
})

describe('isPortalExitReason', () => {
  it.each([
    DisconnectReason.CLIENT_INITIATED,
    DisconnectReason.ROOM_DELETED,
    DisconnectReason.PARTICIPANT_REMOVED,
    DisconnectReason.DUPLICATE_IDENTITY,
  ])('leaves for the portal on reason %s', (reason) => {
    expect(isPortalExitReason(reason)).toBe(true)
  })

  it.each([
    DisconnectReason.JOIN_FAILURE,
    DisconnectReason.SERVER_SHUTDOWN,
    DisconnectReason.CONNECTION_TIMEOUT,
    undefined,
  ])('does not leave on reason %s', (reason) => {
    expect(isPortalExitReason(reason)).toBe(false)
  })
})
