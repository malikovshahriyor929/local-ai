import { NextResponse } from "next/server";
import { proxy } from "@/lib/ai-service";

type RouteContext = { params: Promise<{ filename: string }> };

export async function GET(_: Request, { params }: RouteContext) {
  const { filename } = await params;
  if (!/^tts-[a-f0-9]{32}\.wav$/.test(filename)) {
    return NextResponse.json({ message: "Audio fayl nomi noto‘g‘ri." }, { status: 400 });
  }
  return proxy(`/audio/${filename}`);
}
