import {
  backendUrl,
  downstreamHeaders,
  isAllowedMutation,
  upstreamHeaders,
} from "@/lib/api-proxy";

type RouteContext = { params: Promise<{ path: string[] }> };

async function forward(request: Request, context: RouteContext): Promise<Response> {
  const method = request.method.toUpperCase();
  if (method !== "GET" && !isAllowedMutation(request)) {
    return Response.json(
      { error: { code: "FORBIDDEN", message: "Same-origin request required" } },
      { status: 403, headers: { "Cache-Control": "no-store" } },
    );
  }

  let target: URL;
  try {
    target = backendUrl(request, (await context.params).path);
  } catch {
    return Response.json(
      { error: { code: "BAD_REQUEST", message: "Invalid API path" } },
      { status: 400, headers: { "Cache-Control": "no-store" } },
    );
  }

  try {
    const upstream = await fetch(target, {
      method,
      headers: upstreamHeaders(request),
      body: method === "GET" ? undefined : request.body,
      // Node's fetch requires duplex for a streamed request body.
      duplex: "half",
      redirect: "manual",
      cache: "no-store",
    } as RequestInit & { duplex: "half" });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: downstreamHeaders(upstream),
    });
  } catch {
    return Response.json(
      { error: { code: "SERVICE_UNAVAILABLE", message: "Backend is unavailable" } },
      { status: 503, headers: { "Cache-Control": "no-store" } },
    );
  }
}

export const GET = forward;
export const POST = forward;
export const PATCH = forward;
export const DELETE = forward;
