import { Screen } from '@/layout/Screen'
import { H, P, Link } from '@/primitives'
import { HStack } from '@/styled-system/jsx'
import { useTranslation } from 'react-i18next'

const LegalTermsRoute = () => {
  const { t } = useTranslation('legals')

  return (
    <Screen layout="centered" headerTitle={t('title')}>
      <HStack display={'block'} padding={'2rem'}>
        <H lvl={2}>{t('creator.title')}</H>
        <P>{t('creator.body')}</P>

        <H lvl={2}>{t('hosting.title')}</H>
        <P>{t('hosting.body')}</P>

        <H lvl={2}>{t('accessibility.title')}</H>
        <P>{t('accessibility.body')}</P>
        <P>
          {t('accessibility.more')}
          <Link to="/accessibilite" color="primary">
            {t('accessibility.link')}
          </Link>
        </P>

        <H lvl={2}>{t('software.title')}</H>
        <P>{t('software.body')}</P>
      </HStack>
    </Screen>
  )
}

export default LegalTermsRoute
