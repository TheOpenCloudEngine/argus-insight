import { type NextRequest, NextResponse } from "next/server"

const API_PORT = process.env.API_PORT || "4500"

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const hostname = request.headers.get("host")?.split(":")[0] || "localhost"
  const destination = `http://${hostname}:${API_PORT}${pathname}${search}`

  return NextResponse.rewrite(new URL(destination))
}

export const config = {
  matcher: "/api/v1/:path*",
}
