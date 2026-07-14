import { NextResponse } from "next/server";

const serviceUrl = process.env.AI_SERVICE_URL ?? "http://127.0.0.1:8001";

export async function proxy(path: string, init?: RequestInit) {
  try { return await fetch(`${serviceUrl}${path}`, { ...init, cache: "no-store" }); }
  catch { return NextResponse.json({ code: "AI_SERVICE_UNAVAILABLE", message: "Mahalliy AI xizmati ishlamayapti.", details: serviceUrl, retryable: true }, { status: 503 }); }
}

export async function forward(request: Request, path: string) {
  const response = await proxy(path, { method: request.method, body: request.body, headers: { "content-type": request.headers.get("content-type") ?? "application/json" }, // @ts-expect-error Request streaming is supported by the Next runtime.
    duplex: "half" });
  if (response instanceof NextResponse) return response;
  return new Response(response.body, { status: response.status, headers: { "content-type": response.headers.get("content-type") ?? "application/json", "cache-control": "no-store" } });
}
