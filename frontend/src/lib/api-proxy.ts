const PROXIED_REQUEST_HEADERS = [
  "accept",
  "content-type",
  "cookie",
  "idempotency-key",
  "x-request-id",
];

const PROXIED_RESPONSE_HEADERS = [
  "content-type",
  "set-cookie",
  "retry-after",
  "x-request-id",
];

export function isAllowedMutation(request: Request): boolean {
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin") return false;
  const origin = request.headers.get("origin");
  if (origin) {
    try {
      return new URL(origin).origin === new URL(request.url).origin;
    } catch {
      return false;
    }
  }
  return site === "same-origin";
}

export function backendUrl(request: Request, path: string[]): URL {
  if (path.some((segment) => !segment || segment === "." || segment === ".." || /[/\\]/.test(segment))) {
    throw new Error("Invalid API path");
  }
  const configured = process.env.TSUCHIBOT_BACKEND_URL ?? "http://127.0.0.1:8000";
  const base = new URL(configured);
  if (!["http:", "https:"].includes(base.protocol)) {
    throw new Error("Invalid backend URL protocol");
  }
  const target = new URL(`/api/v1/${path.map(encodeURIComponent).join("/")}`, base);
  target.search = new URL(request.url).search;
  return target;
}

export function upstreamHeaders(request: Request): Headers {
  const headers = new Headers();
  for (const name of PROXIED_REQUEST_HEADERS) {
    const value = request.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  return headers;
}

export function downstreamHeaders(upstream: Response): Headers {
  const headers = new Headers({ "Cache-Control": "no-store" });
  for (const name of PROXIED_RESPONSE_HEADERS) {
    const value = upstream.headers.get(name);
    if (value !== null) headers.set(name, value);
  }
  return headers;
}
