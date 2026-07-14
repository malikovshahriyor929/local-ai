import { forward } from "@/lib/ai-service";
export async function POST(request: Request) { return forward(request, "/api/stt/transcribe"); }
