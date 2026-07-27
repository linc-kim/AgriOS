/**
 * ARIA AI Assistant (Module 13 Part 8) — the complete multimodal workspace.
 *
 * One place to talk, type, speak, and upload images or documents to ARIA. Every
 * reply shows which engine actually answered — a green "deterministic" badge when
 * a local engine handled it, a blue "Gemini" badge only when a model was needed,
 * and "offline" when no provider was configured — so the farmer can see that
 * their numbers were never guessed at.
 *
 * Voice is browser-native (Web Speech): speech-to-text feeds the same pipeline as
 * typing, and ARIA can read its answer back. Where the browser lacks support, the
 * mic simply isn't shown — never a dead button.
 */
import { useRef, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import {
  FileText,
  ImagePlus,
  Loader2,
  Mic,
  MicOff,
  Send,
  ShieldAlert,
  Volume2,
  VolumeX,
} from "lucide-react";

import {
  assist,
  assistImage,
  uploadDocument,
  type AssistResponse,
} from "@/api/ariaAssistant";
import { useVoice, speechLang } from "@/hooks/useVoice";
import { useWorkspace } from "@/shell/useWorkspace";
import { AriaAvatar } from "@/components/aria";
import { cn } from "@/lib/cn";

interface Turn {
  id: string;
  role: "user" | "aria";
  text: string;
  meta?: AssistResponse;
  attachment?: string;
}

const ENGINE_BADGE: Record<string, { label: string; cls: string }> = {
  deterministic: { label: "Deterministic", cls: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300" },
  hybrid: { label: "Deterministic + Gemini", cls: "bg-violet-50 text-violet-700 dark:bg-violet-500/15 dark:text-violet-300" },
  gemini: { label: "Gemini", cls: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300" },
};

const PROVIDER_BADGE: Record<string, string> = {
  offline: "bg-gray-100 text-gray-500 dark:bg-white/10 dark:text-gray-400",
  gemini: "bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300",
  claude: "bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300",
  deterministic: "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300",
};

let _id = 0;
const nextId = () => `t${_id++}`;

export default function AriaAssistantScreen() {
  const { currentFarm } = useWorkspace();
  const farmId = currentFarm?.id;
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [recordState, setRecordState] = useState<Record<string, unknown> | null>(null);
  const [ttsOn, setTtsOn] = useState(false);
  const imageInput = useRef<HTMLInputElement>(null);
  const docInput = useRef<HTMLInputElement>(null);

  const voice = useVoice((finalText) => {
    setInput(finalText);
    send(finalText);
  });

  const push = (t: Turn) => setTurns((prev) => [...prev, t]);

  const ask = useMutation({
    mutationFn: (text: string) => assist(farmId as string, text, recordState),
    onSuccess: (res) => {
      push({ id: nextId(), role: "aria", text: res.answer, meta: res });
      setRecordState((res.data?.state as Record<string, unknown>) ?? null);
      if (ttsOn && res.answer) voice.speak(res.answer, speechLang(res.language));
    },
    onError: () => push({ id: nextId(), role: "aria", text: "Sorry — I couldn't reach the assistant just now." }),
  });

  const imageMut = useMutation({
    mutationFn: (file: File) => assistImage(farmId as string, file, input),
    onSuccess: (res) => push({ id: nextId(), role: "aria", text: res.answer, meta: res }),
  });

  const docMut = useMutation({
    mutationFn: (file: File) => uploadDocument(farmId as string, file),
    onSuccess: (res) => {
      const summary = res.stored
        ? `Stored “${res.filename}” (${res.kind}${res.table_count ? `, ${res.table_count} table(s)` : ""}). ${
            res.deterministic ? "Read it deterministically." : res.note
          } You can now ask me about it.`
        : res.reason;
      push({ id: nextId(), role: "aria", text: summary });
    },
  });

  function send(text?: string) {
    const value = (text ?? input).trim();
    if (!value || !farmId) return;
    push({ id: nextId(), role: "user", text: value });
    setInput("");
    ask.mutate(value);
  }

  if (!farmId) {
    return (
      <p className="py-16 text-center text-sm text-gray-500 dark:text-gray-400">
        Select a farm to talk to ARIA.
      </p>
    );
  }

  const busy = ask.isPending || imageMut.isPending || docMut.isPending;

  return (
    <div className="mx-auto flex h-full max-w-3xl flex-col">
      {/* Header */}
      <header className="flex items-center gap-3 pb-4">
        <AriaAvatar size={40} state={busy ? "thinking" : "idle"} animated />
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
            ARIA Assistant
          </h1>
          <p className="text-[13px] text-gray-500 dark:text-gray-400">
            Talk, type, or upload — English, Kiswahili au Sheng. Deterministic first, always.
          </p>
        </div>
        <button
          type="button"
          onClick={() => { setTtsOn((v) => !v); if (ttsOn) voice.cancelSpeech(); }}
          aria-pressed={ttsOn}
          aria-label={ttsOn ? "Turn off voice replies" : "Turn on voice replies"}
          className={cn(
            "rounded-lg p-2 transition-colors",
            ttsOn ? "bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300"
                  : "text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.06]",
          )}
        >
          {ttsOn ? <Volume2 className="h-5 w-5" /> : <VolumeX className="h-5 w-5" />}
        </button>
      </header>

      {/* Conversation */}
      <div className="flex-1 space-y-4 overflow-y-auto pb-4">
        {turns.length === 0 && (
          <div className="rounded-2xl border border-dashed border-gray-200 p-6 text-center dark:border-white/10">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Try “How many birds died this month?”, “Explain my health report”,
              “Nimepea layers kilo 45 leo”, or upload a receipt.
            </p>
          </div>
        )}
        {turns.map((t) =>
          t.role === "user" ? (
            <div key={t.id} className="flex justify-end">
              <div className="max-w-[85%] rounded-2xl rounded-br-sm bg-brand-600 px-3.5 py-2 text-sm text-white">
                {t.text}
              </div>
            </div>
          ) : (
            <AriaTurn key={t.id} turn={t} />
          ),
        )}
        {busy && (
          <div className="flex items-center gap-2 text-sm text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" /> ARIA is thinking…
          </div>
        )}
      </div>

      {/* Composer */}
      <div className="border-t border-gray-100 pt-3 dark:border-white/[0.06]">
        {voice.listening && (
          <p className="mb-2 flex items-center gap-1.5 text-[12px] text-brand-600 dark:text-brand-400">
            <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" /> Listening… {voice.transcript}
          </p>
        )}
        <div className="flex items-end gap-2">
          <div className="flex gap-1">
            <input ref={imageInput} type="file" accept="image/*" hidden
              onChange={(e) => e.target.files?.[0] && imageMut.mutate(e.target.files[0])} />
            <input ref={docInput} type="file" accept=".csv,.tsv,.xlsx,.xls,.txt,.pdf,.docx" hidden
              onChange={(e) => e.target.files?.[0] && docMut.mutate(e.target.files[0])} />
            <button type="button" onClick={() => imageInput.current?.click()} aria-label="Upload image"
              className="rounded-lg p-2.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.06]">
              <ImagePlus className="h-5 w-5" />
            </button>
            <button type="button" onClick={() => docInput.current?.click()} aria-label="Upload document"
              className="rounded-lg p-2.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.06]">
              <FileText className="h-5 w-5" />
            </button>
            {voice.supported && (
              <button
                type="button"
                onClick={() => (voice.listening ? voice.stop() : voice.start({ continuous: false }))}
                aria-label={voice.listening ? "Stop listening" : "Press to talk"}
                aria-pressed={voice.listening}
                className={cn(
                  "rounded-lg p-2.5 transition-colors",
                  voice.listening ? "bg-red-50 text-red-600 dark:bg-red-500/15 dark:text-red-400"
                                  : "text-gray-400 hover:bg-gray-100 dark:hover:bg-white/[0.06]",
                )}
              >
                {voice.listening ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
              </button>
            )}
          </div>
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
            rows={1}
            placeholder="Ask ARIA anything…"
            aria-label="Message ARIA"
            className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-900 outline-none focus:border-brand-400 dark:border-white/10 dark:bg-white/[0.04] dark:text-white"
          />
          <button
            type="button"
            onClick={() => send()}
            disabled={!input.trim() || busy}
            aria-label="Send"
            className="rounded-xl bg-brand-600 p-2.5 text-white transition-colors hover:bg-brand-700 disabled:opacity-40"
          >
            <Send className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
}

function AriaTurn({ turn }: { turn: Turn }) {
  const m = turn.meta;
  const engine = m ? ENGINE_BADGE[m.engine] : null;
  return (
    <div className="flex justify-start">
      <div className="max-w-[90%] space-y-2">
        <div className="rounded-2xl rounded-bl-sm border border-gray-200 bg-white px-3.5 py-2.5 text-sm text-gray-800 dark:border-white/10 dark:bg-white/[0.03] dark:text-gray-100">
          <p className="whitespace-pre-wrap">{turn.text}</p>
        </div>
        {m && (
          <div className="flex flex-wrap items-center gap-1.5 px-1">
            {engine && (
              <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-semibold", engine.cls)}>
                {engine.label}
              </span>
            )}
            <span className={cn("rounded-full px-2 py-0.5 text-[10px] font-medium", PROVIDER_BADGE[m.provider] ?? PROVIDER_BADGE.offline)}>
              {m.provider}
            </span>
            {m.safety.includes("no_diagnosis") && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                <ShieldAlert className="h-3 w-3" /> see a vet
              </span>
            )}
            {m.sources.length > 0 && (
              <span className="text-[10px] text-gray-400">· {m.sources.join(", ")}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
