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

type ActionResult = { kind: string; value: string; ok: boolean; message?: string };
type Message = {
  role: "user" | "assistant";
  text: string;
  confidence?: string;
  knowledgeStatus?: string;
  audioUrl?: string;
  actions?: ActionResult[];
};
type Status =
  | "Tayyor"
  | "Eshityapman…"
  | "Ovoz yozilmoqda…"
  | "Matnga aylantirilmoqda…"
  | "Javob o‘ylanmoqda…"
  | "Ovoz yaratilmoqda…"
  | "Javob o‘qilmoqda…"
  | "Buyruq bajarilmoqda…"
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
  const [recordingReference, setRecordingReference] = useState(false);
  const [referenceConsent, setReferenceConsent] = useState(false);
  const [referenceMessage, setReferenceMessage] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const referenceRecorder = useRef<MediaRecorder | null>(null);
  const referenceChunks = useRef<Blob[]>([]);
  const audio = useRef<HTMLAudioElement | null>(null);
  const aborter = useRef<AbortController | null>(null);
  const conversationId = useRef(crypto.randomUUID());
  const messageViewport = useRef<HTMLDivElement | null>(null);
  const stickToLatestMessage = useRef(true);

  useEffect(() => {
    if (!stickToLatestMessage.current) return;
    const frame = window.requestAnimationFrame(() => {
      const viewport = messageViewport.current;
      if (viewport) viewport.scrollTo({ top: viewport.scrollHeight, behavior: "smooth" });
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages]);

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
  const playAudio = useCallback((url: string) => {
    if (!url) return;
    audio.current?.pause();
    audio.current = new Audio(url);
    audio.current
      .play()
      .then(() => setStatus("Javob o‘qilmoqda…"))
      .catch(() => setStatus("Tayyor"));
  }, []);
  // The text-chat endpoint streams tokens only. Speaking its answer needs a
  // separate synthesis call; voice-chat already returns audio in its stream.
  const speakAnswer = useCallback(
    async (text: string) => {
      const speechText = text.trim();
      if (!speechText) return;
      setStatus("Ovoz yaratilmoqda…");
      try {
        const response = await fetch("/api/audio/synthesize", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: speechText, language: "uz" }),
        });
        if (!response.ok) throw new Error("tts failed");
        const url = String((await response.json()).audioUrl ?? "");
        setMessages((old) =>
          old.map((m, i) => (i === old.length - 1 ? { ...m, audioUrl: url } : m)),
        );
        playAudio(url);
      } catch {
        // A missing voice must not look like a failed answer.
        setStatus("Tayyor");
      }
    },
    [playAudio],
  );
  const stream = useCallback(async (url: string, body: BodyInit, speak = false) => {
    aborter.current?.abort();
    aborter.current = new AbortController();
    stickToLatestMessage.current = true;
    // JSON string bodies need an explicit Content-Type (fetch defaults to
    // text/plain otherwise, which the API proxy forwards as-is, and FastAPI
    // then rejects since it never parses the body as JSON). FormData bodies
    // (voice recordings) must NOT get an explicit Content-Type - fetch needs
    // to set its own multipart boundary for those.
    const headers =
      typeof body === "string" ? { "Content-Type": "application/json" } : undefined;
    const response = await fetch(url, {
      method: "POST",
      body,
      headers,
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
    let pendingSpeech = "";
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
          playAudio(url);
        }
        if (event === "answer-ready" && !answer.trim())
          appendAnswer(String(data.speechText ?? data.answer ?? ""));
        if (event === "action-started") setStatus("Buyruq bajarilmoqda…");
        if (event === "action-complete") {
          const results = (data.results ?? []) as ActionResult[];
          setMessages((old) =>
            old.map((m, i) => (i === old.length - 1 ? { ...m, actions: results } : m)),
          );
        }
        if (event === "generation-complete" || event === "complete") {
          const spoken = String(data.speechText ?? data.answer ?? answer);
          if (speak && spoken.trim()) pendingSpeech = spoken;
          else setStatus("Tayyor");
        }
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
    // Synthesis runs after the token stream closes so it cannot be cut short
    // by this request's own abort controller.
    if (pendingSpeech) await speakAnswer(pendingSpeech);
  }, [playAudio, speakAnswer]);
  // Typed commands take the same announce-then-execute path as spoken ones.
  const runTypedCommand = async (text: string) => {
    const planResponse = await fetch("/api/actions/plan", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!planResponse.ok) return false;
    const { plan, isConversational } = await planResponse.json();
    if (isConversational || !plan?.summary) return false;
    setMessages((old) => [...old, { role: "assistant", text: String(plan.summary) }]);
    if (plan.requiresConfirmation) {
      setStatus("Tayyor");
      await speakAnswer(String(plan.summary));
      return true;
    }
    setStatus("Buyruq bajarilmoqda…");
    const runResponse = await fetch("/api/actions/execute", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan }),
    });
    const outcome = await runResponse.json().catch(() => ({}));
    setMessages((old) =>
      old.map((m, i) =>
        i === old.length - 1 ? { ...m, actions: (outcome.results ?? []) as ActionResult[] } : m,
      ),
    );
    await speakAnswer(String(plan.summary));
    return true;
  };
  const sendText = async (rawText: string) => {
    const text = rawText.trim();
    if (!text || !isAssistantReady(status)) return;
    audio.current?.pause();
    stickToLatestMessage.current = true;
    setPrompt("");
    setMessages((old) => [...old, { role: "user", text }]);
    setStatus("Javob o‘ylanmoqda…");
    try {
      // A recognised command is carried out instead of being chatted about.
      if (await runTypedCommand(text)) return;
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
        true,
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
  const submitText = async (event: FormEvent) => {
    event.preventDefault();
    await sendText(prompt);
  };
  const ttsNeedsVoiceSample = Boolean(
    health?.tts?.referenceAudioRequired && !health?.tts?.referenceAudioExists,
  );
  const toggleReferenceRecording = async () => {
    if (recordingReference) {
      referenceRecorder.current?.stop();
      return;
    }
    if (!referenceConsent) {
      setReferenceMessage("Davom etish uchun rozilik katagini belgilang.");
      return;
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      referenceChunks.current = [];
      const current = new MediaRecorder(media, {
        mimeType: MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : undefined,
      });
      referenceRecorder.current = current;
      current.ondataavailable = (event) => referenceChunks.current.push(event.data);
      current.onstop = async () => {
        media.getTracks().forEach((track) => track.stop());
        setRecordingReference(false);
        setReferenceMessage("Ovoz namunasi saqlanmoqda…");
        const form = new FormData();
        form.append(
          "file",
          new Blob(referenceChunks.current, { type: current.mimeType }),
          "reference.webm",
        );
        form.append("consent", "true");
        try {
          const response = await fetch("/api/audio/reference", {
            method: "POST",
            body: form,
          });
          const result = await response.json();
          if (!response.ok)
            throw new Error(result.message ?? "Ovoz namunasi saqlanmadi.");
          setHealth((currentHealth) =>
            currentHealth
              ? {
                  ...currentHealth,
                  tts: { ...currentHealth.tts, referenceAudioExists: true },
                }
              : currentHealth,
          );
          setReferenceMessage(
            "Ovoz namunasi tayyor. Endi mikrofonli chat audio javob beradi.",
          );
        } catch (error) {
          setReferenceMessage((error as Error).message);
        }
      };
      current.start(250);
      setRecordingReference(true);
      setReferenceMessage(
        "3–15 soniya tabiiy ovozda gapiring, so‘ng to‘xtatish tugmasini bosing.",
      );
    } catch {
      setReferenceMessage("Mikrofonga ruxsat berilmadi yoki ovoz yozib bo‘lmadi.");
    }
  };
  const startRecording = async () => {
    if (ttsNeedsVoiceSample) {
      setReferenceMessage(
        "Avval pastdagi ovoz namunasini sozlang, so‘ng mikrofonli chat ishlaydi.",
      );
      return;
    }
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
    <main className="h-dvh overflow-hidden p-3 md:p-5">
      <div className="mx-auto grid h-full min-h-0 max-w-[1600px] grid-cols-1 gap-3 xl:grid-cols-[270px_minmax(0,1fr)_310px]">
        <aside className="panel hidden min-h-0 rounded-2xl p-4 xl:flex xl:flex-col">
          <div className="mb-5 flex items-center gap-2">
            <Bot className="text-indigo-300" />
            <span className="font-semibold">Uzbek Local Voice AI</span>
          </div>
          <Button
            variant="secondary"
            className="justify-start"
            onClick={() => {
              conversationId.current = crypto.randomUUID();
              stickToLatestMessage.current = true;
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
        <section className="panel flex h-full min-h-0 flex-col overflow-hidden rounded-2xl">
          <header className="z-10 flex shrink-0 items-center justify-between border-b bg-slate-950/15 p-4 backdrop-blur-sm">
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
          <div
            ref={messageViewport}
            data-testid="chat-scroll-region"
            onScroll={(event) => {
              const viewport = event.currentTarget;
              stickToLatestMessage.current =
                viewport.scrollHeight - viewport.scrollTop - viewport.clientHeight < 96;
            }}
            className="min-h-0 flex-1 overscroll-contain overflow-y-auto p-4 md:p-7"
          >
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
                  <Button
                    type="button"
                    variant="secondary"
                    className="mt-5"
                    disabled={!isAssistantReady(status)}
                    onClick={() => void sendText("Salom! Nimalarga yordam bera olasiz?")}
                  >
                    Sinov savolini yuborish
                  </Button>
                </div>
              )}
              {messages.map((message, index) => (
                <article
                  key={`${message.role}-${index}`}
                  className={
                    message.role === "user"
                      ? "ml-auto max-w-[85%] rounded-2xl rounded-br-sm bg-indigo-500/25 px-4 py-3 shadow-sm shadow-indigo-950/30"
                      : "max-w-[88%] rounded-2xl rounded-bl-sm border border-indigo-300/15 bg-slate-900/65 px-4 py-3 shadow-sm shadow-black/20"
                  }
                >
                  {message.role === "assistant" && (
                    <div className="mb-2 flex items-center gap-2 text-xs font-medium text-indigo-200">
                      <span className="flex size-6 items-center justify-center rounded-lg bg-indigo-400/15">
                        <Bot className="size-3.5" />
                      </span>
                      Mahalliy yordamchi
                    </div>
                  )}
                  <p className="whitespace-pre-wrap break-words text-[15px] leading-7 text-slate-100">
                    {message.text || <span className="text-slate-500">…</span>}
                  </p>
                  {message.actions?.length ? (
                    <ul className="mt-3 space-y-1 border-t border-indigo-300/10 pt-3">
                      {message.actions.map((action, actionIndex) => (
                        <li
                          key={`${action.kind}-${actionIndex}`}
                          className={`flex items-start gap-2 text-xs ${action.ok ? "text-emerald-300" : "text-rose-300"}`}
                        >
                          <span aria-hidden>{action.ok ? "✓" : "✕"}</span>
                          <span>{action.message || `${action.kind}: ${action.value}`}</span>
                        </li>
                      ))}
                    </ul>
                  ) : null}
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
              <div aria-hidden="true" />
            </div>
          </div>
          <div className="z-10 shrink-0 border-t bg-slate-950/15 p-3 backdrop-blur-sm md:p-5">
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
            {ttsNeedsVoiceSample && (
              <div className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-sm">
                <p className="font-medium text-amber-100">Audio javobni yoqish</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">
                  TTS uchun 3–15 soniyalik ruxsatli ovoz namunasi kerak. U faqat shu qurilmada saqlanadi.
                </p>
                <label className="mt-3 flex cursor-pointer items-start gap-2 text-xs leading-5 text-slate-300">
                  <input
                    type="checkbox"
                    checked={referenceConsent}
                    onChange={(event) => setReferenceConsent(event.target.checked)}
                    className="mt-1 accent-indigo-400"
                  />
                  Ovoz namunamdan mahalliy yordamchi javoblarini o‘qish uchun foydalanishga roziman.
                </label>
                <Button
                  type="button"
                  variant={recordingReference ? "default" : "secondary"}
                  className="mt-3"
                  disabled={!recordingReference && !referenceConsent}
                  onClick={() => void toggleReferenceRecording()}
                >
                  {recordingReference ? (
                    <CircleStop data-icon="inline-start" />
                  ) : (
                    <Mic data-icon="inline-start" />
                  )}
                  {recordingReference
                    ? "Namunani to‘xtatish"
                    : "Ovoz namunasini yozish"}
                </Button>
                {referenceMessage && (
                  <p className="mt-2 text-xs leading-5 text-slate-300">
                    {referenceMessage}
                  </p>
                )}
              </div>
            )}
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
                    (value?.modelExists
                      ? "Model topildi"
                      : healthFailed
                      ? "Mahalliy AI xizmati ishlamayapti"
                      : "Tekshirilmoqda…")}
                </p>
                <p className="mt-1 text-xs text-slate-500">
                  {value?.loaded
                    ? "Yuklangan"
                    : value?.modelExists
                      ? "Tayyor (so‘rovda yuklanadi)"
                      : "Model topilmadi"}
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
          <Button variant="ghost" className="mt-4 w-full" onClick={() => { window.location.href = "/mening-ovozim"; }}>
            <Settings data-icon="inline-start" />
            Sozlamalar
          </Button>
        </aside>
      </div>
    </main>
  );
}
