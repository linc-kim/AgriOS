/**
 * Greena — install-to-home-screen state.
 *
 * Wraps the browser's native install prompt where it exists (Chromium's
 * `beforeinstallprompt`) and, everywhere else, tells the UI which platform the
 * visitor is on so it can show the right hand-instructions. It also detects when
 * Greena is already running from the home screen, so we stop asking.
 *
 * No dependencies, no analytics — just the small amount of state the install
 * guide and the "Install Greena" buttons need.
 */
import { useCallback, useEffect, useState } from "react";

export type Platform = "android" | "ios" | "ipados" | "desktop";

/** The non-standard event Chromium fires before offering installation. */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

function detectPlatform(): Platform {
  if (typeof navigator === "undefined") return "desktop";
  const ua = navigator.userAgent || "";
  if (/android/i.test(ua)) return "android";
  if (/iphone|ipod/i.test(ua)) return "ios";
  // iPadOS 13+ reports a desktop Safari UA; the touch points give it away.
  if (/ipad/i.test(ua) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1)) {
    return "ipados";
  }
  return "desktop";
}

function detectStandalone(): boolean {
  if (typeof window === "undefined") return false;
  const displayModeStandalone = window.matchMedia?.("(display-mode: standalone)")?.matches;
  // iOS Safari exposes navigator.standalone instead of the display-mode query.
  const iosStandalone = (window.navigator as Navigator & { standalone?: boolean }).standalone === true;
  return Boolean(displayModeStandalone || iosStandalone);
}

export interface PwaInstall {
  /** Best-guess platform; the UI still lets the user switch manually. */
  platform: Platform;
  /** True when Greena is already launched from the home screen. */
  isStandalone: boolean;
  /** True when the browser offers a one-tap native install right now. */
  canPromptInstall: boolean;
  /** Set once the app has been installed during this session. */
  installed: boolean;
  /** Trigger the native install dialog. Returns the user's choice, or null. */
  promptInstall: () => Promise<"accepted" | "dismissed" | null>;
}

export function usePwaInstall(): PwaInstall {
  const [deferred, setDeferred] = useState<BeforeInstallPromptEvent | null>(null);
  const [isStandalone, setStandalone] = useState<boolean>(detectStandalone);
  const [installed, setInstalled] = useState(false);
  const [platform] = useState<Platform>(detectPlatform);

  useEffect(() => {
    const onBeforeInstall = (e: Event) => {
      e.preventDefault(); // keep the browser from showing its own mini-infobar
      setDeferred(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setDeferred(null);
    };
    const mq = window.matchMedia?.("(display-mode: standalone)");
    const onDisplayChange = () => setStandalone(detectStandalone());

    window.addEventListener("beforeinstallprompt", onBeforeInstall);
    window.addEventListener("appinstalled", onInstalled);
    mq?.addEventListener?.("change", onDisplayChange);

    return () => {
      window.removeEventListener("beforeinstallprompt", onBeforeInstall);
      window.removeEventListener("appinstalled", onInstalled);
      mq?.removeEventListener?.("change", onDisplayChange);
    };
  }, []);

  const promptInstall = useCallback(async () => {
    if (!deferred) return null;
    await deferred.prompt();
    const { outcome } = await deferred.userChoice;
    setDeferred(null); // a prompt can only be used once
    return outcome;
  }, [deferred]);

  return {
    platform,
    isStandalone,
    canPromptInstall: Boolean(deferred),
    installed,
    promptInstall,
  };
}
