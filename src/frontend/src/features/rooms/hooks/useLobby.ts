import { useCallback, useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { keys } from '@/api/queryKeys'
import { type ApiRefusal } from '@/api/apiRefusal'
import {
  requestEntry,
  ApiLobbyStatus,
  type ApiRequestEntry,
} from '../api/requestEntry'
import { setLobbyParticipantId } from '@/stores/lobby'
import { getEntryOutcome } from '../utils/entryError'

export const WAIT_TIMEOUT_MS = 600000 // 10 minutes
export const POLL_INTERVAL_MS = 3_000

export const useLobby = ({
  roomId,
  username,
  onAccepted,
}: {
  roomId: string
  username: string
  onAccepted: (e: ApiRequestEntry) => void
}) => {
  const [status, setStatus] = useState(ApiLobbyStatus.IDLE)
  const [refusal, setRefusal] = useState<ApiRefusal | undefined>()
  const waitingTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const clearWaitingTimeout = useCallback(() => {
    if (waitingTimeoutRef.current) {
      clearTimeout(waitingTimeoutRef.current)
      waitingTimeoutRef.current = null
    }
  }, [])

  const startWaitingTimeout = useCallback(() => {
    clearWaitingTimeout()
    waitingTimeoutRef.current = setTimeout(() => {
      setStatus(ApiLobbyStatus.TIMEOUT)
    }, WAIT_TIMEOUT_MS)
  }, [clearWaitingTimeout])

  const { data: waitingData } = useQuery({
    queryKey: [keys.requestEntry, roomId],
    queryFn: async () => {
      try {
        const response = await requestEntry({
          roomId,
          username,
        })

        if (response.id) {
          setLobbyParticipantId(roomId, response.id)
        }
        if (response.status === ApiLobbyStatus.ACCEPTED) {
          clearWaitingTimeout()
          setStatus(ApiLobbyStatus.ACCEPTED)
          onAccepted(response)
        } else if (response.status === ApiLobbyStatus.DENIED) {
          clearWaitingTimeout()
          setStatus(ApiLobbyStatus.DENIED)
        }
        return response
      } catch (error) {
        // Room deleted or entry refused (e.g. quota used up), for anonymous
        // users too: stop polling, show why
        const outcome = getEntryOutcome(error)
        if (outcome) {
          clearWaitingTimeout()
          if (outcome.status === ApiLobbyStatus.REFUSED) {
            setRefusal(outcome.refusal)
          }
          setStatus(outcome.status)
          return { status: outcome.status }
        }
        throw error
      }
    },
    refetchInterval: POLL_INTERVAL_MS,
    refetchOnWindowFocus: false,
    refetchIntervalInBackground: true,
    enabled: status === ApiLobbyStatus.WAITING,
  })

  // Refusal met before waiting (room retrieval): nothing to poll.
  const refuse = useCallback(
    (apiRefusal: ApiRefusal) => {
      clearWaitingTimeout()
      setRefusal(apiRefusal)
      setStatus(ApiLobbyStatus.REFUSED)
    },
    [clearWaitingTimeout]
  )

  const startWaiting = useCallback(() => {
    setStatus(ApiLobbyStatus.WAITING)
    startWaitingTimeout()
  }, [startWaitingTimeout])

  useEffect(() => {
    return () => clearWaitingTimeout()
  }, [clearWaitingTimeout])

  return {
    status,
    refusal,
    refuse,
    startWaiting,
    waitingData,
  }
}
