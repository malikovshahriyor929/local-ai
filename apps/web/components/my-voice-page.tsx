"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Check, CircleStop, Mic, Play, RefreshCw, RotateCcw, Volume2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type Voice = { speaker_id: string; referenceReady: boolean; active: boolean; datasetCount: number; reference_transcript?: string };
type Pending = { blob: Blob; url: string; kind: "reference" | "dataset" } | null;

const speakerId = "shahriyor";

async function api(path: string, init?: RequestInit) {
  const response = await fetch(`/api/voices/${path}`, init);
  const data = await response.json();
  if (!response.ok) throw new Error(data.message ?? "Mahalliy xizmat xatosi");
  return data;
}

export function MyVoicePage() {
  const [voice, setVoice] = useState<Voice | null>(null);
  const [sentences, setSentences] = useState<string[]>([]);
  const [index, setIndex] = useState(0);
  const [transcript, setTranscript] = useState("");
  const [autoTranscript, setAutoTranscript] = useState(false);
  const [consent, setConsent] = useState(false);
  const [pending, setPending] = useState<Pending>(null);
  const [recording, setRecording] = useState<"reference" | "dataset" | null>(null);
  const [notice, setNotice] = useState("");
  const [jobStatus, setJobStatus] = useState("");
  const [checkpoint, setCheckpoint] = useState("models/tts/uzbek-voice/checkpoint-epoch-0");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const refresh = async () => {
    const data = await api("");
    setVoice(data.voices.find((item: Voice) => item.speaker_id === speakerId) ?? null);
    setSentences(data.sentences ?? []);
  };
  useEffect(() => { void refresh().catch((error) => setNotice(error.message)); }, []);

  const start = async (kind: "reference" | "dataset") => {
    if (kind === "reference" && !consent) return setNotice("Avval ovozdan foydalanishga rozilik bering.");
    const media = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks.current = [];
    const current = new MediaRecorder(media, { mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : undefined });
    recorder.current = current;
    current.ondataavailable = (event) => chunks.current.push(event.data);
    current.onstop = () => {
      media.getTracks().forEach((track) => track.stop());
      const blob = new Blob(chunks.current, { type: current.mimeType });
      setPending((old) => { if (old) URL.revokeObjectURL(old.url); return { blob, url: URL.createObjectURL(blob), kind }; });
      setRecording(null);
      setNotice(kind === "reference" ? "Namuna tayyor: eshiting, transcriptni tekshiring va saqlang." : "Dataset yozuvi tayyor: eshiting, so‘ng qabul qiling yoki qayta yozing.");
    };
    current.start(250);
    setRecording(kind);
    setNotice(kind === "reference" ? "3–15 soniya tabiiy ovozda gapiring." : `Jumlani aynan o‘qing: ${sentences[index]}`);
  };
  const stop = () => recorder.current?.state === "recording" && recorder.current.stop();
  const formFor = (blob: Blob) => { const form = new FormData(); form.append("file", blob, "voice.webm"); return form; };

  const create = async () => { await api("", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ speakerId }) }); await refresh(); setNotice("`shahriyor` speaker yaratildi."); };
  const saveReference = async () => {
    if (!pending || pending.kind !== "reference") return;
    const form = formFor(pending.blob); form.append("transcript", transcript); form.append("autoTranscribe", String(autoTranscript)); form.append("consent", "true");
    const result = await api(`${speakerId}/reference`, { method: "POST", body: form });
    setTranscript(result.referenceTranscript); setPending(null); await refresh(); setNotice("Reference audio saqlandi va clone prompt keshi yangilandi.");
  };
  const acceptDataset = async () => {
    if (!pending || pending.kind !== "dataset") return;
    const form = formFor(pending.blob); form.append("sentenceIndex", String(index)); form.append("text", sentences[index]);
    const result = await api(`${speakerId}/dataset/clip`, { method: "POST", body: form });
    setPending(null); setIndex((value) => Math.min(value + 1, sentences.length - 1)); await refresh();
    setNotice(result.quality.silence || result.quality.clipping ? "Yozuv saqlandi, ammo sifat ogohlantirishi bor — qayta yozish tavsiya etiladi." : "Yozuv qabul qilindi; metadata.jsonl va train_raw.jsonl yangilandi.");
  };
  const testVoice = async () => { const result = await api(`${speakerId}/test`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ text: "Assalomu alaykum, bu Shahriyor ovozining sinovi." }) }); new Audio(result.audioUrl).play(); setNotice("Haqiqiy Uzbek WAV yaratildi."); };
  const job = async (path: string) => {
    const result = await api(`${speakerId}/${path}`, { method: "POST" });
    setJobStatus("Navbatda…");
    setNotice(`Job boshlandi: ${result.jobId}. Bu oynani ochiq qoldiring.`);
    const timer = window.setInterval(() => {
      void api(`jobs/${result.jobId}`).then((status) => {
        setJobStatus(status.status === "complete" ? "Tayyor" : status.status === "failed" ? "Xatolik — logni terminalda tekshiring" : "Bajarilmoqda…");
        if (status.status === "complete" || status.status === "failed") window.clearInterval(timer);
      }).catch(() => window.clearInterval(timer));
    }, 2500);
  };
  const activateCheckpoint = async () => {
    const result = await api(`${speakerId}/training/activate`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ checkpoint }) });
    await refresh();
    setNotice(`Checkpoint faollashdi: ${result.checkpoint}. Keyingi WAV shu modeldan yaratiladi.`);
  };

  return <main className="min-h-screen p-4 md:p-7"><div className="mx-auto max-w-4xl space-y-5">
    <header className="panel rounded-2xl p-5"><a href="/" className="inline-flex items-center gap-1 text-sm text-indigo-200 hover:text-white"><ArrowLeft className="size-4"/>Yordamchiga qaytish</a><p className="mt-4 text-sm text-indigo-200">Mening ovozim</p><h1 className="mt-1 text-2xl font-semibold">Shahriyor uchun lokal ovoz profili</h1><p className="mt-2 text-sm text-slate-400">Zero-shot clone va Qwen3-TTS 0.6B fine-tuning uchun barcha ma’lumot faqat shu qurilmada saqlanadi.</p></header>
    {!voice ? <section className="panel rounded-2xl p-5"><Button onClick={() => void create()}><Check data-icon="inline-start"/>`shahriyor` speaker yaratish</Button></section> : <>
      <section className="panel rounded-2xl p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="font-semibold">1. Zero-shot reference audio</h2><p className="mt-1 text-sm text-slate-400">Reference: {voice.referenceReady ? "tayyor" : "hali yozilmagan"}</p></div>{voice.active && <Badge className="text-emerald-300">Default assistant voice</Badge>}</div>
        <label className="mt-4 flex gap-2 text-sm text-slate-300"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="accent-indigo-400"/>O‘z ovozimdan lokal clone va fine-tuning uchun foydalanishga roziman.</label>
        <textarea value={transcript} onChange={(event) => setTranscript(event.target.value)} placeholder="Reference audio aniq transkripti" className="mt-3 min-h-20 w-full rounded-xl border bg-slate-950/40 p-3 text-sm outline-none" />
        <label className="mt-2 flex gap-2 text-xs text-slate-400"><input type="checkbox" checked={autoTranscript} onChange={(event) => setAutoTranscript(event.target.checked)} />Transcriptni STT orqali avtomatik olish</label>
        <div className="mt-3 flex flex-wrap gap-2"><Button disabled={recording === "dataset"} onClick={() => recording === "reference" ? stop() : void start("reference")}>{recording === "reference" ? <CircleStop data-icon="inline-start"/> : <Mic data-icon="inline-start"/>}{recording === "reference" ? "To‘xtatish" : "Yozish / almashtirish"}</Button>{pending?.kind === "reference" && <><Button variant="secondary" onClick={() => new Audio(pending.url).play()}><Play data-icon="inline-start"/>Eshitish</Button><Button variant="secondary" onClick={() => void saveReference()}><Check data-icon="inline-start"/>Saqlash</Button></>} {voice.referenceReady && <><Button variant="secondary" onClick={() => void testVoice()}><Volume2 data-icon="inline-start"/>Real WAV sinovi</Button><Button variant="secondary" onClick={() => void api(`${speakerId}/activate`, { method: "POST" }).then(refresh)}><Check data-icon="inline-start"/>Default qilish</Button></>}</div>
      </section>
      <section className="panel rounded-2xl p-5"><h2 className="font-semibold">2. Fine-tuning dataset</h2><p className="mt-1 text-sm text-slate-400">{voice.datasetCount} ta qabul qilingan yozuv. Har jumlani aynan o‘qing.</p><div className="mt-4 rounded-xl border bg-slate-950/35 p-4"><Badge>{index + 1} / {sentences.length}</Badge><p className="mt-3 text-lg leading-8">{sentences[index]}</p><div className="mt-4 flex flex-wrap gap-2"><Button disabled={!voice.referenceReady || recording === "reference"} onClick={() => recording === "dataset" ? stop() : void start("dataset")}>{recording === "dataset" ? <CircleStop data-icon="inline-start"/> : <Mic data-icon="inline-start"/>}{recording === "dataset" ? "To‘xtatish" : "Jumlani yozish"}</Button>{pending?.kind === "dataset" && <><Button variant="secondary" onClick={() => new Audio(pending.url).play()}><Play data-icon="inline-start"/>Eshitish</Button><Button variant="secondary" onClick={() => void acceptDataset()}><Check data-icon="inline-start"/>Qabul qilish</Button><Button variant="ghost" onClick={() => setPending(null)}><RotateCcw data-icon="inline-start"/>Qayta yozish</Button></>}<Button variant="ghost" onClick={() => setIndex((value) => Math.min(value + 1, sentences.length - 1))}>O‘tkazib yuborish</Button></div></div>
        <div className="mt-4 flex flex-wrap gap-2"><Button variant="secondary" disabled={voice.datasetCount < 2} onClick={() => void job("dataset/extract-codes")}><RefreshCw data-icon="inline-start"/>audio_codes ajratish</Button><Button variant="secondary" disabled={voice.datasetCount < 2} onClick={() => void job("training/smoke-test")}>0.6B smoke test</Button></div>
        <div className="mt-4 rounded-xl border border-indigo-300/15 bg-slate-950/25 p-3"><p className="text-sm font-medium">Checkpointni faollashtirish</p><p className="mt-1 text-xs text-slate-400">Smoke test tugagach checkpoint yo‘lini tasdiqlang. Faollashgandan keyin “Real WAV sinovi” fine-tuned checkpointni qayta yuklab tekshiradi.</p><div className="mt-3 flex flex-wrap gap-2"><input value={checkpoint} onChange={(event) => setCheckpoint(event.target.value)} className="min-w-64 flex-1 rounded-lg border bg-slate-950/50 px-3 py-2 text-sm"/><Button variant="secondary" onClick={() => void activateCheckpoint()}>Checkpointni default qilish</Button></div>{jobStatus && <p className="mt-2 text-xs text-indigo-200">Fine-tune job: {jobStatus}</p>}</div>
      </section></>}
    {notice && <p className="rounded-xl border border-indigo-300/15 bg-indigo-400/5 p-3 text-sm text-slate-200">{notice}</p>}
  </div></main>;
}
