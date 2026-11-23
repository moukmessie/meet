import { useConfig } from '@/api/useConfig'
import { usePortalUrl } from '@/features/portal/usePortal'

export const useTelephony = () => {
  const { data } = useConfig()
  // Fork patch: with a portal, the dial-in number and the PIN code are hidden
  const portalUrl = usePortalUrl()

  if (portalUrl || !data?.telephony?.enabled) {
    return {
      enabled: false,
    }
  }

  return {
    enabled: data?.telephony?.enabled,
    country: data?.telephony.default_country,
    internationalPhoneNumber: data?.telephony.international_phone_number,
  }
}
