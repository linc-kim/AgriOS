/**
 * useVoice — browser speech-to-text and text-to-speech for ARIA (Module 13 Part 8).
 *
 * Speech recognition and synthesis run entirely in the browser via the Web Speech
 * API, so voice never leaves the device for transcription and works with no server
 * STT. It degrades honestly: on a browser without support, `supported` is false and
 * the UI hides the mic rather than pretending to listen.
 *
 * Language follows the farmer — Swahili gets `sw-KE`/`sw-TZ` voices when present,
 * otherwise the default — because a trilingual farm should hear ARIA in its own
 * tongue where the platform allows it.
 */
import { useCallback, useEffect, useRef, useState } from "react";

// ── Minimal Web Speech API typings ───────────────────────────────────────────
// These aren't in the default DOM lib, so we declare the slice we use.
interface SpeechRecognitionAlternative {
  transcript: string;
}
interface SpeechRecognitionResult {
  isFinal: boolean;
  0: SpeechRecognitionAlternative;
}
interface SpeechRecognitionResultList {
  length: number;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionEvent {
  resultIndex: number;
  results: SpeechRecognitionResultList;
}
interface SpeechRecognition {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
}

type SpeechRecognitionCtor = new () => SpeechRecognition;

function getRecognition(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

export interface UseVoice {
  supported: boolean;
  listening: boolean;
  speaking: boolean;
  transcript: string;
  start: (opts?: { lang?: string; continuous?: boolean }) => void;
  stop: () => void;
  speak: (text: string, lang?: string) => void;
  cancelSpeech: () => void;
}

/** Map ARIA's language code to a BCP-47 tag for the speech APIs. */
export function speechLang(code: string): string {
  if (code === "sw" || code === "sheng") return "sw-KE";
  return "en-US";
}

export function useVoice(onFinal?: (text: string) => void): UseVoice {
  const Recognition = getRecognition();
  const sttSupported = !!Recognition;
  const ttsSupported = typeof window !== "undefined" && "speechSynthesis" in window;

  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [transcript, setTranscript] = useState("");
  const recRef = useRef<SpeechRecognition | null>(null);
  const onFinalRef = useRef(onFinal);
  onFinalRef.current = onFinal;

  const stop = useCallback(() => {
    recRef.current?.stop();
    setListening(false);
  }, []);

  const start = useCallback(
    (opts?: { lang?: string; continuous?: boolean }) => {
      if (!Recognition) return;
      const rec = new Recognition();
      rec.lang = opts?.lang ?? "en-US";
      rec.continuous = opts?.continuous ?? false;
      rec.interimResults = true;
      rec.onresult = (e: SpeechRecognitionEvent) => {
        let finalText = "";
        let interim = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i];
          if (r.isFinal) finalText += r[0].transcript;
          else interim += r[0].transcript;
        }
        setTranscript(finalText || interim);
        if (finalText) {
          onFinalRef.current?.(finalText.trim());
          if (!rec.continuous) setListening(false);
        }
      };
      rec.onerror = () => setListening(false);
      rec.onend = () => setListening(false);
      recRef.current = rec;
      setTranscript("");
      setListening(true);
      rec.start();
    },
    [Recognition],
  );

  const speak = useCallback(
    (text: string, lang?: string) => {
      if (!ttsSupported || !text) return;
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      if (lang) u.lang = lang;
      u.onstart = () => setSpeaking(true);
      u.onend = () => setSpeaking(false);
      u.onerror = () => setSpeaking(false);
      window.speechSynthesis.speak(u);
    },
    [ttsSupported],
  );

  const cancelSpeech = useCallback(() => {
    if (ttsSupported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }, [ttsSupported]);

  useEffect(() => () => {
    recRef.current?.stop();
    if (ttsSupported) window.speechSynthesis.cancel();
  }, [ttsSupported]);

  return {
    supported: sttSupported,
    listening,
    speaking,
    transcript,
    start,
    stop,
    speak,
    cancelSpeech,
  };
}
