import { describe, expect, it, vi } from 'vitest'

vi.mock('@/features/rooms', () => ({ flexibleRoomIdPattern: '[a-z-]+' }))

import { routes } from './routes'

describe('routes hidden when a portal is configured', () => {
  it('hides home, feedback and the SDK screens, and keeps the room', () => {
    const hidden = Object.values(routes)
      .filter((route) => route.hiddenWithPortal)
      .map((route) => route.name)
      .sort()
    expect(hidden).toEqual(
      [
        'feedback',
        'home',
        'sdkCreateButton',
        'sdkCreatePopup',
        'sdkSettingsPopup',
      ].sort()
    )
    expect(routes.room.hiddenWithPortal).toBeUndefined()
  })
})
