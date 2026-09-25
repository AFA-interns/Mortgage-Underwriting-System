export type AuthenticatedUser = { name: string; email: string } | null

export function getAuthenticatedUser(): AuthenticatedUser {
  return null
}
