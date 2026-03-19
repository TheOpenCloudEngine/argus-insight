export interface SessionUser {
  id: number
  firstName: string
  lastName: string
  username: string
  email: string
  phone: string
  role: string
}

export interface Session {
  user: SessionUser
}
