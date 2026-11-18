import { describe, expect, it, vi } from 'vitest'
import { DataPacket, UserPacket } from '@livekit/protocol'
import { EngineEvent, Room, RoomEvent } from 'livekit-client'
import { listenMeetingEnding, type DataPacketLike } from './useMeetingEnding'

const payload = new TextEncoder().encode(
  JSON.stringify({
    type: 'meetingEnding',
    data: { seconds_left: 100, reason: 'duration_limit' },
  })
)

// What the receiving client sees, as observed against livekit-server 1.13.11
// with livekit-client 2.21 (the SDK copies the user packet identity to the
// packet level before emitting).
const serverPacket = (): DataPacketLike => ({
  participantIdentity: '',
  participantSid: '',
  value: { case: 'user', value: { payload, participantIdentity: '' } },
})
const clientPacket = (): DataPacketLike => ({
  participantIdentity: 'mallory',
  participantSid: 'PA_mallory',
  value: { case: 'user', value: { payload, participantIdentity: 'mallory' } },
})

type Listener = (packet: DataPacketLike) => void
class FakeEngine {
  listeners = new Set<Listener>()
  on(_event: string, listener: Listener) {
    this.listeners.add(listener)
  }
  off(_event: string, listener: Listener) {
    this.listeners.delete(listener)
  }
  emit(_event: string, packet: DataPacketLike) {
    this.listeners.forEach((listener) => listener(packet))
  }
}

const setup = () => {
  const engine = new FakeEngine()
  const onEnding = vi.fn()
  const stop = listenMeetingEnding(engine as never, onEnding)
  const receive = (packet: DataPacketLike) =>
    engine.emit(EngineEvent.DataPacketReceived, packet)
  return { engine, onEnding, stop, receive }
}

describe('listenMeetingEnding', () => {
  it('accepts a packet sent by the server API', () => {
    const { onEnding, receive } = setup()
    receive(serverPacket())
    expect(onEnding).toHaveBeenCalledTimes(1)
    expect(onEnding.mock.calls[0][0]).toMatchObject({
      reason: 'duration_limit',
    })
  })

  // Forgery: a client message received before the sender is registered in
  // room.remoteParticipants reaches RoomEvent.DataReceived with an undefined
  // participant, but the raw packet still carries the sender identity.
  it('rejects a packet forged by a participant', () => {
    const { onEnding, receive } = setup()
    receive(clientPacket())
    expect(onEnding).not.toHaveBeenCalled()
  })

  it('rejects a packet with only the sender sid or the user identity', () => {
    const { onEnding, receive } = setup()
    receive({ ...serverPacket(), participantSid: 'PA_x' })
    receive({
      ...serverPacket(),
      value: { case: 'user', value: { payload, participantIdentity: 'x' } },
    })
    expect(onEnding).not.toHaveBeenCalled()
  })

  it('ignores packets that are not user packets', () => {
    const { onEnding, receive } = setup()
    receive({ ...serverPacket(), value: { case: 'chatMessage' } })
    expect(onEnding).not.toHaveBeenCalled()
  })

  it('stops listening and fails closed without an engine', () => {
    const { engine, onEnding, stop, receive } = setup()
    stop()
    receive(serverPacket())
    expect(onEnding).not.toHaveBeenCalled()
    expect(engine.listeners.size).toBe(0)
    expect(() => listenMeetingEnding(undefined, onEnding)()).not.toThrow()
  })
})

// Pins the SDK behavior that made the previous `if (participant) return` check
// forgeable, and checks the fix against a real Room.
describe('with a real livekit-client Room', () => {
  const forgedFromUnknownSender = () =>
    new DataPacket({
      participantIdentity: 'mallory',
      participantSid: 'PA_mallory',
      value: { case: 'user', value: new UserPacket({ payload }) },
    })

  it('gives an undefined participant to a client message from a not yet known sender', () => {
    const room = new Room()
    const onData = vi.fn()
    room.on(RoomEvent.DataReceived, onData)
    room.engine.emit(
      EngineEvent.DataPacketReceived,
      forgedFromUnknownSender(),
      0
    )
    // The old check would have accepted this message as a server one.
    expect(onData).toHaveBeenCalledTimes(1)
    expect(onData.mock.calls[0][1]).toBeUndefined()
  })

  it('still rejects that message, and accepts a server one', () => {
    const room = new Room()
    const onEnding = vi.fn()
    listenMeetingEnding(room.engine, onEnding)
    room.engine.emit(
      EngineEvent.DataPacketReceived,
      forgedFromUnknownSender(),
      0
    )
    expect(onEnding).not.toHaveBeenCalled()
    room.engine.emit(
      EngineEvent.DataPacketReceived,
      new DataPacket({
        value: { case: 'user', value: new UserPacket({ payload }) },
      }),
      0
    )
    expect(onEnding).toHaveBeenCalledTimes(1)
  })
})
