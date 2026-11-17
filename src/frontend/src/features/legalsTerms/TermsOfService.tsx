import { Screen } from '@/layout/Screen'
import { H, P } from '@/primitives'
import { HStack } from '@/styled-system/jsx'
import { useTranslation } from 'react-i18next'

type Article = { title: string; paragraphs: string[] }

const TermsOfServiceRoute = () => {
  const { t } = useTranslation('termsOfService')
  const articles = t('articles', { returnObjects: true }) as Article[]

  return (
    <Screen layout="centered" headerTitle={t('title')}>
      <HStack display={'block'} padding={'2rem'}>
        {Array.isArray(articles) &&
          articles.map((article, index) => (
            <section key={index}>
              <H lvl={2}>{`${index + 1}. ${article.title}`}</H>
              {article.paragraphs.map((paragraph, i) => (
                <P key={i}>{paragraph}</P>
              ))}
            </section>
          ))}
      </HStack>
    </Screen>
  )
}

export default TermsOfServiceRoute
