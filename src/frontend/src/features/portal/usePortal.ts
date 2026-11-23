import { useCallback } from 'react'
import { useConfig } from '@/api/useConfig'
import { useUser } from '@/features/auth/api/useUser'
import {
  getPortalExitUrl,
  getPortalHomeUrl,
  normalizePortalUrl,
} from './portalUrl'

/** Portal origin from the configuration, or null (upstream behaviour). */
export const usePortalUrl = () => {
  const { data } = useConfig()
  return normalizePortalUrl(data?.portal_url)
}

/** Portal home address, or null (upstream behaviour). */
export const usePortalHomeUrl = () => {
  const { data } = useConfig()
  return getPortalHomeUrl(data?.portal_url)
}

/**
 * Leaves the room for the portal. Returns false (and does nothing) when no
 * portal is configured, so the caller falls back to the upstream behaviour.
 */
export const useLeaveToPortal = () => {
  const { data } = useConfig()
  const { isLoggedIn } = useUser()
  return useCallback((): boolean => {
    const target = getPortalExitUrl(data?.portal_url, isLoggedIn === true)
    if (!target) return false
    window.location.assign(target)
    return true
  }, [data?.portal_url, isLoggedIn])
}
