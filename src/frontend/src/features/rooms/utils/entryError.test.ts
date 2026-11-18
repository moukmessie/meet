import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api/ApiError'
import { ApiLobbyStatus } from '../api/requestEntry'
import { getEntryOutcome } from './entryError'

describe('getEntryOutcome', () => {
  it('stops the wait with the refusal of a 403 (quota used up)', () => {
    const body = {
      detail: 'Quota épuisé',
      code: 'monthly_minutes_exhausted',
      quota: { limit: 6000, resets_at: '2026-12-01T00:00:00Z' },
    }
    expect(getEntryOutcome(new ApiError(403, body))).toEqual({
      status: ApiLobbyStatus.REFUSED,
      refusal: body,
    })
  })

  it('flags a deleted room (410)', () => {
    expect(getEntryOutcome(new ApiError(410, {}))).toEqual({
      status: ApiLobbyStatus.DELETED,
    })
  })

  it('keeps the other errors for the caller (polling retries)', () => {
    expect(getEntryOutcome(new ApiError(500, {}))).toBeUndefined()
    expect(getEntryOutcome(new ApiError(429, {}))).toBeUndefined()
    expect(getEntryOutcome(new Error('network'))).toBeUndefined()
  })
})
