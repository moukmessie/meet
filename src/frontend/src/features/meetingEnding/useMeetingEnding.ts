import { useEffect, useState } from 'react'
import { useRoomContext } from '@livekit/components-react'
import { EngineEvent, type Room } from 'livekit-client'
import { decodeMeetingEnding, type MeetingEnding } from './meetingEnding'

/**
 * The part of a LiveKit data packet needed to tell who sent it. The LiveKit
 * server stamps `participantIdentity` / `participantSid` with the sender's
 * identity on every packet it forwards from a client (a client cannot
 * override them), and leaves them empty on packets sent through the server API
 * (`RoomService.SendData`), which is how the platform sends this notification.
 */
export type DataPacketLike = {
  participantIdentity?: string
  participantSid?: string
  value: { case?: string; value?: unknown }
}

type UserPacketLike = { payload?: Uint8Array; participantIdentity?: string }

/**
 * Payload of a user data packet sent by the server API (no sender at all), or
 * undefined for any other packet.
 * This is decided on the raw packet, never on the `participant` argument of
 * `RoomEvent.DataReceived`: that one is `undefined` for a server message, but
 * also for a client message received before the sender is registered in
 * `room.remoteParticipants`, so it cannot prove the message comes from the
 * server.
 */
export const getServerPayload = (
  packet: DataPacketLike
): Uint8Array | undefined => {
  if (packet.value?.case !== 'user') return
  if (packet.participantIdentity || packet.participantSid) return
  const user = packet.value.value as UserPacketLike | undefined
  if (user?.participantIdentity) return
  return user?.payload instanceof Uint8Array ? user.payload : undefined
}

type PacketSource = Pick<Room['engine'], 'on' | 'off'>

/**
 * Call `onMeetingEnding` for each valid `meetingEnding` notification sent by
 * the server. Returns the function that stops listening.
 */
export const listenMeetingEnding = (
  engine: PacketSource | undefined,
  onMeetingEnding: (meetingEnding: MeetingEnding) => void
): (() => void) => {
  // Fail closed: without access to the raw packets, nothing is accepted.
  if (!engine) return () => {}
  const handlePacket = (packet: DataPacketLike) => {
    const payload = getServerPayload(packet)
    if (!payload) return
    const decoded = decodeMeetingEnding(payload)
    if (decoded) onMeetingEnding(decoded)
  }
  engine.on(EngineEvent.DataPacketReceived, handlePacket)
  return () => {
    engine.off(EngineEvent.DataPacketReceived, handlePacket)
  }
}

/**
 * Listen to the `meetingEnding` notification sent by the platform (data message
 * without topic). Other notification types are ignored, so the existing
 * notification listeners are unaffected.
 * Only messages sent by the server are accepted (see `getServerPayload`), so
 * that a participant cannot forge the banner.
 */
export const useMeetingEnding = (): MeetingEnding | undefined => {
  const room = useRoomContext()
  const [meetingEnding, setMeetingEnding] = useState<MeetingEnding>()

  useEffect(() => listenMeetingEnding(room.engine, setMeetingEnding), [room])

  return meetingEnding
}
