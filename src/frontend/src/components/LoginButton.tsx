import { LinkButton } from '@/primitives'
import { useTranslation } from 'react-i18next'
import { usePortalUrl } from '@/features/portal/usePortal'
import { authUrl } from '@/features/auth/utils/authUrl'

export const LoginButton = () => {
  const { t } = useTranslation('global', { keyPrefix: 'login' })
  // Fork patch: with a portal, sign-in happens there, never from Meet
  const portalUrl = usePortalUrl()
  if (portalUrl) return null

  return (
    <LinkButton href={authUrl()} data-attr="login" variant="primary">
      {t('buttonLabel')}
    </LinkButton>
  )
}
