import { forward, proxy } from "@/lib/ai-service";

export async function GET() {
  return proxy("/api/voices");
}

export async function POST(request: Request) {
  return forward(request, "/api/voices");
}
