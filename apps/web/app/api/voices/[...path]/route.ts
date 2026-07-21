import { forward, proxy } from "@/lib/ai-service";

type RouteContext = { params: Promise<{ path: string[] }> };

async function upstreamPath(params: RouteContext["params"]) {
  const { path } = await params;
  return `/api/voices/${path.map(encodeURIComponent).join("/")}`;
}

export async function GET(_: Request, { params }: RouteContext) {
  return proxy(await upstreamPath(params));
}

export async function POST(request: Request, { params }: RouteContext) {
  return forward(request, await upstreamPath(params));
}
