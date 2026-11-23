import { ApiAccessLevel } from '@/features/rooms/api/ApiRoom'

const ACCESS_LEVEL_RANK: Record<ApiAccessLevel, number> = {
  [ApiAccessLevel.PUBLIC]: 0,
  [ApiAccessLevel.TRUSTED]: 1,
  [ApiAccessLevel.RESTRICTED]: 2,
}

/**
 * Whether a room can be switched from `current` to `target`. When the harden-only
 * policy is off (upstream behavior) every level is allowed; when it is on, only the
 * current level and stricter ones are (public < trusted < restricted).
 */
export const isAccessLevelAllowed = (
  current: ApiAccessLevel | undefined,
  target: ApiAccessLevel,
  hardenOnly?: boolean
): boolean => {
  if (!hardenOnly || !current) return true
  return ACCESS_LEVEL_RANK[target] >= ACCESS_LEVEL_RANK[current]
}
