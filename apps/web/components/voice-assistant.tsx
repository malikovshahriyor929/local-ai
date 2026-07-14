"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import {
  Bot,
  CircleStop,
  Cpu,
  Mic,
  Plus,
  Send,
  Settings,
  Square,
  Volume2,
  X,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { isAssistantReady } from "@/lib/local-status";

type Message = {
  role: "user" | "assistant";
  text: string;
  confidence?: string;
  knowledgeStatus?: string;
  audioUrl?: string;
};
type Status =
  | "Tayyor"
  | "Eshityapman…"
  | "Ovoz yozilmoqda…"
  | "Matnga aylantirilmoqda…"
  | "Javob o‘ylanmoqda…"
  | "Ovoz yaratilmoqda…"
  | "Javob o‘qilmoqda…"
  | "Xatolik yuz berdi";
const initialMessages: Message[] = [];

function parseEvents(
  buffer: string,
  onEvent: (event: string, value: Record<string, unknown>) => void,
) {
  const blocks = buffer.split("\n\n");
  const rest = blocks.pop() ?? "";
  for (const block of blocks) {
    const event = block.match(/^event: (.+)$/m)?.[1];
    const data = block.match(/^data: (.+)$/m)?.[1];
    if (event && data)
      try {
        onEvent(event, JSON.parse(data));
      } catch {
        /* ignore a malformed event */
      }
  }
  return rest;
}

export function VoiceAssistant() {
  const [messages, setMessages] = useState<Message[]>(initialMessages);
  const [prompt, setPrompt] = useState("");
  const [status, setStatus] = useState<Status>("Tayyor");
  const [health, setHealth] = useState<Record<string, any> | null>(null);
  const [healthFailed, setHealthFailed] = useState(false);
  const [recording, setRecording] = useState(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const audio = useRef<HTMLAudioElement | null>(null);
  const aborter = useRef<AbortController | null>(null);
  const conversationId = useRef(crypto.randomUUID());

  useEffect(() => {
    let active = true;
    const checkHealth = () =>
      fetch("/api/system/health")
        .then((response) => {
          if (!response.ok) throw new Error("health failed");
          return response.json();
        })
        .then((data) => {
          if (active) {
            setHealth(data);
            setHealthFailed(false);
          }
        })
        .catch(() => {
          if (active) {
            setHealth(null);
            setHealthFailed(true);
          }
        });
    void checkHealth();
    const timer = window.setInterval(checkHealth, 5_000);
    return () => {
      active = false;
      window.clearInterval(timer);
      aborter.current?.abort();
      audio.current?.pause();
    };
  }, []);
  const stream = useCallback(async (url: string, body: BodyInit) => {
    aborter.current?.abort();
    aborter.current = new AbortController();
    const response = await fetch(url, {
      method: "POST",
      body,
      signal: aborter.current.signal,
    });
    if (!response.ok || !response.body)
      throw new Error(
        (await response.json().catch(() => ({}))).message ??
          "Xatolik yuz berdi",
      );
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    const appendAnswer = (token: string) => {
      answer += token;
      setMessages((old) => {
        const previous = old.at(-1);
        return previous?.role === "assistant"
          ? [...old.slice(0, -1), { ...previous, text: answer }]
          : [...old, { role: "assistant", text: answer }];
      });
    };
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = parseEvents(buffer, (event, data) => {
        if (event === "token" || event === "answer-token")
          appendAnswer(String(data.token ?? ""));
        if (event === "transcription-ready")
          setMessages((old) => [
            ...old,
            {
              role: "user",
              text: String(data.normalizedText ?? data.text ?? ""),
            },
          ]);
        if (event === "tts-started") setStatus("Ovoz yaratilmoqda…");
        if (event === "audio-ready") {
          const url = String(data.audioUrl ?? "");
          setMessages((old) =>
            old.map((m, i) =>
              i === old.length - 1 ? { ...m, audioUrl: url } : m,
            ),
          );
          if (url) {
            audio.current = new Audio(url);
            audio.current
              .play()
              .then(() => setStatus("Javob o‘qilmoqda…"))
              .catch(() => setStatus("Tayyor"));
          }
        }
        if (event === "generation-complete" || event === "complete")
          setStatus("Tayyor");
        if (event === "generation-error" || event === "error") {
          setStatus("Xatolik yuz berdi");
          setMessages((old) => [
            ...old,
            {
              role: "assistant",
              text: String(data.message ?? "Xatolik yuz berdi"),
            },
          ]);
        }
      });
    }
  }, []);
  const submitText = async (event?: FormEvent) => {
    event?.preventDefault();
    const text = prompt.trim();
    if (!text || !isAssistantReady(status)) return;
    setPrompt("");
    setMessages((old) => [...old, { role: "user", text }]);
    setStatus("Javob o‘ylanmoqda…");
    try {
      await stream(
        "/api/chat",
        JSON.stringify({
          conversationId: conversationId.current,
          messages: [
            ...messages.map(({ role, text }) => ({ role, content: text })),
            { role: "user", content: text },
          ],
          language: "uz",
        }),
      );
    } catch (error) {
      if ((error as Error).name !== "AbortError") {
        setStatus("Xatolik yuz berdi");
        setMessages((old) => [
          ...old,
          { role: "assistant", text: (error as Error).message },
        ]);
      }
    }
  };
  const startRecording = async () => {
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks.current = [];
      const current = new MediaRecorder(media, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : undefined,
      });
      recorder.current = current;
      current.ondataavailable = (event) => chunks.current.push(event.data);
      current.onstop = async () => {
        media.getTracks().forEach((track) => track.stop());
        setRecording(false);
        setStatus("Matnga aylantirilmoqda…");
        const form = new FormData();
        form.append(
          "file",
          new Blob(chunks.current, { type: current.mimeType }),
          "voice.webm",
        );
        form.append("conversationId", conversationId.current);
        try {
          await stream("/api/voice-chat", form);
        } catch (error) {
          if ((error as Error).name !== "AbortError")
            setStatus("Xatolik yuz berdi");
        }
      };
      current.start(250);
      setRecording(true);
      setStatus("Ovoz yozilmoqda…");
    } catch {
      setStatus("Xatolik yuz berdi");
    }
  };
  const stop = () =>
    recorder.current?.state === "recording"
      ? recorder.current.stop()
      : aborter.current?.abort();
  const local = health?.offlineMode ? "Oflayn rejim" : "Mahalliy loyiha";
  const system = health?.system;
  return (
    <main className="min-h-screen p-3 md:p-5">
      <div className="mx-auto grid min-h-[calc(100vh-1.5rem)] max-w-[1600px] grid-cols-1 gap-3 xl:grid-cols-[270px_minmax(0,1fr)_310px]">
        <aside className="panel hidden rounded-2xl p-4 xl:flex xl:flex-col">
          <div className="mb-5 flex items-center gap-2">
            <Bot className="text-indigo-300" />
            <span className="font-semibold">Uzbek Local Voice AI</span>
          </div>
          <Button
            variant="secondary"
            className="justify-start"
            onClick={() => {
              conversationId.current = crypto.randomUUID();
              setMessages([]);
            }}
          >
            <Plus data-icon="inline-start" />
            Yangi suhbat
          </Button>
          <div className="mt-5 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Suhbatlar
          </div>
          <div className="mt-3 rounded-xl border border-border bg-slate-900/40 p-3 text-sm text-slate-400">
            Yangi mahalliy suhbat
          </div>
          <p className="mt-auto text-xs leading-5 text-slate-500">
            Suhbatlar faqat ushbu qurilmada saqlanadi.
          </p>
        </aside>
        <section className="panel flex min-h-[80vh] flex-col overflow-hidden rounded-2xl">
          <header className="flex items-center justify-between border-b p-4">
            <div>
              <h1 className="text-lg font-semibold">
                Mahalliy o‘zbek yordamchi
              </h1>
              <p className="text-xs text-slate-400">
                Internetga ulanmasdan ishlaydi
              </p>
            </div>
            <Badge className="gap-2">
              <span className="size-2 rounded-full bg-emerald-400" />
              {local}
            </Badge>
          </header>
          <div className="flex-1 overflow-y-auto p-4 md:p-7">
            <div className="mx-auto flex max-w-3xl flex-col gap-5">
              {messages.length === 0 && (
                <div className="my-auto pt-20 text-center">
                  <div className="mx-auto mb-5 flex size-16 items-center justify-center rounded-2xl bg-indigo-500/15">
                    <Mic className="text-indigo-300" />
                  </div>
                  <h2 className="text-xl font-semibold">Suhbatni boshlang</h2>
                  <p className="mt-2 text-sm text-slate-400">
                    Savol yozing yoki mikrofon tugmasini bosing.
                  </p>
                </div>
              )}
              {messages.map((message, index) => (
                <article
                  key={`${message.role}-${index}`}
                  className={
                    message.role === "user"
                      ? "ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-500/25 px-4 py-3"
                      : "max-w-[88%] rounded-2xl rounded-bl-sm border bg-slate-900/55 px-4 py-3"
                  }
                >
                  <p className="whitespace-pre-wrap leading-7 text-slate-100">
                    {message.text || <span className="text-slate-500">…</span>}
                  </p>
                  {message.role === "assistant" && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {message.confidence && (
                        <Badge>ishonch: {message.confidence}</Badge>
                      )}
                      {message.knowledgeStatus && (
                        <Badge>bilim: {message.knowledgeStatus}</Badge>
                      )}
                      {message.audioUrl && (
                        <Button
                          variant="ghost"
                          className="h-7 px-2 text-xs"
                          onClick={() => {
                            audio.current = new Audio(message.audioUrl);
                            audio.current.play();
                          }}
                        >
                          <Volume2 data-icon="inline-start" />
                          Qayta eshiting
                        </Button>
                      )}
                    </div>
                  )}
                </article>
              ))}
            </div>
          </div>
          <div className="border-t p-3 md:p-5">
            <div className="mb-2 flex items-center justify-between px-1 text-xs text-slate-400">
              <span>{status}</span>
              {recording && <span className="text-rose-300">● Yozilmoqda</span>}
            </div>
            {recording && (
              <div className="wave mb-3 flex h-8 items-center justify-center gap-1">
                {Array.from({ length: 35 }, (_, i) => (
                  <i key={i} style={{ height: `${10 + (i % 7) * 3}px` }} />
                ))}
              </div>
            )}
            <form
              onSubmit={submitText}
              className="flex items-center gap-2 rounded-2xl border bg-slate-950/40 p-2"
            >
              <Button
                type="button"
                variant={recording ? "default" : "secondary"}
                className="size-11 rounded-xl p-0"
                onClick={recording ? stop : startRecording}
                aria-label={recording ? "Ovozni to‘xtatish" : "Ovoz yozish"}
              >
                {recording ? <Square /> : <Mic />}
              </Button>
              <input
                value={prompt}
                onChange={(event) => setPrompt(event.target.value)}
                disabled={!isAssistantReady(status)}
                className="min-w-0 flex-1 bg-transparent px-2 py-2 text-sm outline-none placeholder:text-slate-500"
                placeholder="Savolingizni o‘zbek tilida yozing…"
              />
              <Button
                type="submit"
                className="size-11 rounded-xl p-0"
                disabled={!prompt.trim() || !isAssistantReady(status)}
                aria-label="Yuborish"
              >
                <Send />
              </Button>
              {!isAssistantReady(status) && (
                <Button
                  type="button"
                  variant="ghost"
                  className="size-10 rounded-xl p-0"
                  onClick={stop}
                  aria-label="To‘xtatish"
                >
                  <X />
                </Button>
              )}
            </form>
          </div>
        </section>
        <aside className="panel rounded-2xl p-4">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">Tizim holati</h2>
            <Badge
              className={healthFailed ? "text-rose-300" : "text-emerald-300"}
            >
              {healthFailed
                ? "Xizmat ulanmagan"
                : health
                  ? "Tayyor"
                  : "Tekshirilmoqda…"}
            </Badge>
          </div>
          <div className="flex flex-col gap-3">
            {[
              ["LLM", health?.llm],
              ["STT", health?.stt],
              ["TTS", health?.tts],
            ].map(([name, value]) => (
              <div
                className="rounded-xl border bg-slate-950/25 p-3"
                key={String(name)}
              >
                <div className="flex items-center gap-2">
                  <Cpu className="text-indigo-300" />
                  <span className="font-medium">{name}</span>
                  <span
                    className={`ml-auto size-2 rounded-full ${healthFailed ? "bg-rose-400" : "bg-emerald-400"}`}
                  />
                </div>
                <p className="mt-2 truncate text-xs text-slate-400">
                  {value?.path ??
                    (healthFailed
                      ? "Mahalliy AI xizmati ishlamayapti"
                      : "Tekshirilmoqda…")}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {value?.loaded ? "Yuklangan" : "Hali yuklanmagan"}
                </p>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl border bg-slate-950/25 p-3">
            <p className="text-sm font-medium">Qurilma resurslari</p>
            <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
              <div>
                <p className="text-slate-500">GPU</p>
                <p className="mt-1 font-medium">
                  {system?.gpu ?? "Aniqlanmoqda"}
                </p>
              </div>
              <div>
                <p className="text-slate-500">RAM</p>
                <p className="mt-1 font-medium">
                  {system
                    ? `${system.ramUsedMb} / ${system.ramTotalMb} MB`
                    : "—"}
                </p>
              </div>
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Backend: {system?.selectedBackend ?? "—"}
            </p>
          </div>
          <Button variant="ghost" className="mt-4 w-full">
            <Settings data-icon="inline-start" />
            Sozlamalar
          </Button>
        </aside>
      </div>
    </main>
  );
}
