import { Screen } from '@/layout/Screen'
import { H, P } from '@/primitives'
import { HStack } from '@/styled-system/jsx'
import { useTranslation } from 'react-i18next'

const AccessibilityRoute = () => {
  const { t } = useTranslation('accessibility', { keyPrefix: 'accessibility' })

  return (
    <Screen layout="centered" headerTitle={t('title')}>
      <HStack display={'block'} padding={'2rem'}>
        <P>{t('introduction')}</P>

        <H lvl={2} bold>
          {t('declaration.title')}
        </H>

        <H lvl={2} bold>
          {t('complianceStatus.title')}
        </H>
        <P>{t('complianceStatus.body')}</P>

        <H lvl={2} bold>
          {t('improvement.title')}
        </H>
        <P>{t('improvement.body')}</P>
      </HStack>
    </Screen>
  )
}

export default AccessibilityRoute
