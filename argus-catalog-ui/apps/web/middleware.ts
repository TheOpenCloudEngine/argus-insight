import { type NextRequest, NextResponse } from "next/server"

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:4600"

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const destination = `${API_BASE_URL}${pathname}${search}`

  try {
    const backendResponse = await fetch(destination, {
      method: request.method,
      headers: request.headers,
      body: request.method !== "GET" && request.method !== "HEAD" ? request.body : undefined,
      // @ts-expect-error -- Next.js supports duplex for streaming request bodies
      duplex: "half",
    })

    const responseHeaders = new Headers(backendResponse.headers)
    responseHeaders.delete("transfer-encoding")

    return new NextResponse(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    })
  } catch {
    return NextResponse.json(
      { detail: "Backend server is unreachable. Please check if catalog-server is running." },
      { status: 502 },
    )
  }
}

export const config = {
  matcher: "/api/v1/:path*",
}
