import { type NextRequest, NextResponse } from "next/server"

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:4500"

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const destination = `${API_BASE_URL}${pathname}${search}`

  return NextResponse.rewrite(new URL(destination))
}

export const config = {
  matcher: "/api/v1/:path*",
}
