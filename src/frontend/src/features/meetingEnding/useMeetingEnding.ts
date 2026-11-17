import { useEffect, useState } from 'react'
import { useRoomContext } from '@livekit/components-react'
import { RoomEvent, type RemoteParticipant } from 'livekit-client'
import { decodeMeetingEnding, type MeetingEnding } from './meetingEnding'

/**
 * Listen to the `meetingEnding` notification sent by the platform (data message
 * without topic). Other notification types are ignored, so the existing
 * notification listeners are unaffected.
 * Only messages sent by the server (no sender participant) are accepted, so
 * that a participant cannot forge the banner.
 */
export const useMeetingEnding = (): MeetingEnding | undefined => {
  const room = useRoomContext()
  const [meetingEnding, setMeetingEnding] = useState<MeetingEnding>()

  useEffect(() => {
    const handleDataReceived = (
      payload: Uint8Array,
      participant?: RemoteParticipant
    ) => {
      if (participant) return
      const decoded = decodeMeetingEnding(payload)
      if (decoded) setMeetingEnding(decoded)
    }
    room.on(RoomEvent.DataReceived, handleDataReceived)
    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived)
    }
  }, [room])

  return meetingEnding
}
