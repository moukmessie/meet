import { type ComponentType, type LazyExoticComponent } from 'react'
import { useConfig } from '@/api/useConfig'
import { getPortalHomeUrl } from './portalUrl'
import { useEffect } from 'react'

/**
 * Fork patch: screen of Meet that duplicates the portal (home, creation,
 * feedback, SDK). Without `portal_url` it renders the upstream screen. With it,
 * the visitor is sent to the portal home, a fixed address from the
 * configuration.
 */
export const PortalHiddenRoute = ({
  Component,
}: {
  Component: LazyExoticComponent<ComponentType> | ComponentType
}) => {
  const { data, isLoading } = useConfig()
  const target = getPortalHomeUrl(data?.portal_url)

  useEffect(() => {
    if (target) window.location.replace(target)
  }, [target])

  // never flash the Meet screen while the configuration is loading
  if (isLoading || target) return null
  return <Component />
}
