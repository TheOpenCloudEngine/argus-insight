/**
 * API proxy middleware — forwards /api/v1/* to argus-rag-server.
 */
import { NextRequest, NextResponse } from "next/server";

const API_BASE_URL = process.env.API_BASE_URL || "http://localhost:4800";

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const destination = `${API_BASE_URL}${pathname}${search}`;

  const backendResponse = await fetch(destination, {
    method: request.method,
    headers: request.headers,
    body:
      request.method !== "GET" && request.method !== "HEAD"
        ? request.body
        : undefined,
    // @ts-expect-error duplex needed for streaming
    duplex: "half",
  });

  return new NextResponse(backendResponse.body, {
    status: backendResponse.status,
    headers: new Headers(backendResponse.headers),
  });
}

export const config = {
  matcher: "/api/v1/:path*",
};
