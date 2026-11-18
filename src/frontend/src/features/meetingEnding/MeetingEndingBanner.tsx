import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { css } from '@/styled-system/css'
import { getCountdown, type MeetingEnding } from './meetingEnding'
import { useMeetingEnding } from './useMeetingEnding'

const TICK_MS = 1000

export const MeetingEndingBanner = () => {
  const meetingEnding = useMeetingEnding()
  if (!meetingEnding) return null
  return <Banner meetingEnding={meetingEnding} />
}

const Banner = ({ meetingEnding }: { meetingEnding: MeetingEnding }) => {
  const { t } = useTranslation('rooms', { keyPrefix: 'meetingEnding' })
  const [now, setNow] = useState(() => Date.now())

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), TICK_MS)
    return () => clearInterval(interval)
  }, [])

  const countdown = getCountdown(meetingEnding.endsAt, now)
  const message =
    countdown.kind === 'minutes'
      ? t('minute', { count: countdown.minutes })
      : countdown.kind === 'lessThanMinute'
        ? t('lessThanMinute')
        : t('ended')

  return (
    // The text only changes once per minute: the live region stays calm.
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      data-testid="meeting-ending-banner"
      className={css({
        position: 'fixed',
        top: '1rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 1000,
        maxWidth: 'min(32rem, calc(100vw - 2rem))',
        padding: '0.75rem 1rem',
        borderRadius: '0.5rem',
        backgroundColor: 'warning.subtle',
        color: 'warning.subtle-text',
        border: '1px solid',
        borderColor: 'warning',
        boxShadow: '0 2px 8px rgba(0, 0, 0, 0.2)',
        textAlign: 'center',
      })}
    >
      <p className={css({ fontWeight: 'bold' })}>{message}</p>
      <p className={css({ fontSize: '0.875rem' })}>
        {t(`reasons.${meetingEnding.reason}`)}
      </p>
    </div>
  )
}
