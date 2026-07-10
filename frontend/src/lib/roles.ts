/**
 * Greena — Role derivation helpers
 *
 * The API returns a user's roles as `user_roles: UserRole[]` (each optionally
 * scoped to a farm). Platform-level roles (super_admin, platform_admin) carry
 * `farm_id === null`. These helpers derive the single role values the UI needs
 * (admin gating, profile display) from that array — there is no top-level
 * `role` field on the user object.
 */

import type { RoleName, User } from "@/types";

type UserLike = Pick<User, "user_roles"> | null | undefined;

/** The user's platform-level role name (farm_id === null), or null if none. */
export function platformRole(user: UserLike): RoleName | null {
  const platform = user?.user_roles?.find((ur) => ur.farm_id === null);
  return platform?.role.name ?? null;
}

/** True if the user holds the super_admin role. */
export function isSuperAdmin(user: UserLike): boolean {
  return (user?.user_roles ?? []).some((ur) => ur.role.name === "super_admin");
}
