import { proxy } from "@/lib/ai-service";
export async function GET() { const response = await proxy("/api/system/models"); if (response instanceof Response && "body" in response) return response; return response; }
