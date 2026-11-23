import { describe, expect, it } from 'vitest'
import { ApiAccessLevel } from '@/features/rooms/api/ApiRoom'
import { isAccessLevelAllowed } from './accessLevel'

const { PUBLIC, TRUSTED, RESTRICTED } = ApiAccessLevel

describe('isAccessLevelAllowed', () => {
  it('allows every level when the policy is off', () => {
    for (const current of [PUBLIC, TRUSTED, RESTRICTED]) {
      for (const target of [PUBLIC, TRUSTED, RESTRICTED]) {
        expect(isAccessLevelAllowed(current, target, false)).toBe(true)
        expect(isAccessLevelAllowed(current, target, undefined)).toBe(true)
      }
    }
  })

  it('only offers the current and stricter levels when the policy is on', () => {
    expect(isAccessLevelAllowed(PUBLIC, PUBLIC, true)).toBe(true)
    expect(isAccessLevelAllowed(PUBLIC, TRUSTED, true)).toBe(true)
    expect(isAccessLevelAllowed(PUBLIC, RESTRICTED, true)).toBe(true)
    expect(isAccessLevelAllowed(TRUSTED, PUBLIC, true)).toBe(false)
    expect(isAccessLevelAllowed(TRUSTED, RESTRICTED, true)).toBe(true)
    expect(isAccessLevelAllowed(RESTRICTED, TRUSTED, true)).toBe(false)
    expect(isAccessLevelAllowed(RESTRICTED, PUBLIC, true)).toBe(false)
  })

  it('offers everything while the current level is unknown', () => {
    expect(isAccessLevelAllowed(undefined, PUBLIC, true)).toBe(true)
  })
})
