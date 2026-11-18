import { ApiError } from '@/api/ApiError'
import { getApiRefusal, type ApiRefusal } from '@/api/apiRefusal'
import { ApiLobbyStatus } from '../api/requestEntry'

export type EntryOutcome =
  | { status: ApiLobbyStatus.DELETED }
  | { status: ApiLobbyStatus.REFUSED; refusal: ApiRefusal }

/**
 * Classify an error of the entry request (initial call and polling) that must
 * stop the wait: room deleted (410) or entry refused (403, e.g. monthly quota
 * used up), for anonymous and authenticated users alike. Any other error is
 * left to the caller (returns undefined).
 */
export const getEntryOutcome = (error: unknown): EntryOutcome | undefined => {
  if (error instanceof ApiError && error.statusCode === 410) {
    return { status: ApiLobbyStatus.DELETED }
  }
  const refusal = getApiRefusal(error)
  if (refusal) {
    return { status: ApiLobbyStatus.REFUSED, refusal }
  }
  return undefined
}
