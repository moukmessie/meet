import { useTranslation } from 'react-i18next'
import { MenuItem, Menu as RACMenu } from 'react-aria-components'
import { Button, Menu } from '@/primitives'
import { navigateTo } from '@/navigation/navigateTo'
import { generateRoomId, useCreateRoom } from '@/features/rooms'
import { RiAddLine, RiLink } from '@remixicon/react'
import { LaterMeetingDialog } from '@/features/home/components/LaterMeetingDialog'
import { useState } from 'react'

import { menuRecipe } from '@/primitives/menuRecipe'
import { ApiRoom } from '@/features/rooms/api/ApiRoom'
import { useSnapshot } from 'valtio'
import { userStore } from '@/stores/user'
import { getApiRefusal, getRefusalMessage } from '@/api/apiRefusal'
import { css } from '@/styled-system/css'

export const CreateMeetingMenu = () => {
  const { username } = useSnapshot(userStore)

  const { t, i18n } = useTranslation('home')
  const { t: tRooms } = useTranslation('rooms')
  const { mutateAsync: createRoom } = useCreateRoom()
  const [laterRoom, setLaterRoom] = useState<null | ApiRoom>(null)
  const [refusalMessage, setRefusalMessage] = useState<string | null>(null)

  const handleCreateError = (error: unknown) => {
    const refusal = getApiRefusal(error)
    if (!refusal) throw error
    setRefusalMessage(getRefusalMessage(refusal, tRooms, i18n.language))
  }

  return (
    <>
      <Menu>
        <Button variant="primary" data-attr="create-meeting">
          {t('createMeeting')}
        </Button>
        <RACMenu>
          <MenuItem
            className={menuRecipe({ icon: true, variant: 'light' }).item}
            onAction={() => {
              const slug = generateRoomId()
              setRefusalMessage(null)
              createRoom({ slug, username })
                .then((data) =>
                  navigateTo('room', data.slug, {
                    state: { create: true, initialRoomData: data },
                  })
                )
                .catch(handleCreateError)
            }}
            data-attr="create-option-instant"
          >
            <RiAddLine size={18} />
            {t('createMenu.instantOption')}
          </MenuItem>
          <MenuItem
            className={menuRecipe({ icon: true, variant: 'light' }).item}
            onAction={() => {
              const slug = generateRoomId()
              setRefusalMessage(null)
              createRoom({ slug, username })
                .then(setLaterRoom)
                .catch(handleCreateError)
            }}
            data-attr="create-option-later"
          >
            <RiLink size={18} />
            {t('createMenu.laterOption')}
          </MenuItem>
        </RACMenu>
      </Menu>
      {refusalMessage && (
        <p
          role="alert"
          className={css({ marginTop: '0.5rem', color: 'danger.700' })}
        >
          {refusalMessage}
        </p>
      )}
      <LaterMeetingDialog
        room={laterRoom}
        onOpenChange={() => setLaterRoom(null)}
      />
    </>
  )
}
