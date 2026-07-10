/**
 * Greena — Sentry Initialisation
 *
 * Sprint 10 (Production Hardening): Frontend error monitoring.
 * AD-14 (Frozen): Sentry is the error monitoring platform for Greena V1.
 *
 * Initialised before React renders so all errors — including those during
 * module evaluation — are captured.
 *
 * Only active when VITE_SENTRY_DSN is set (i.e. staging + production).
 * Development runs without Sentry to keep the console clean.
 */

import * as Sentry from "@sentry/react";

const DSN = import.meta.env.VITE_SENTRY_DSN as string | undefined;
const ENVIRONMENT = import.meta.env.VITE_ENVIRONMENT as string | undefined;
const isDev = ENVIRONMENT === "development" || import.meta.env.DEV;

export function initialiseSentry(): void {
  if (!DSN || isDev) {
    return;
  }

  Sentry.init({
    dsn: DSN,
    environment: ENVIRONMENT ?? "production",
    release: `agrios-frontend@1.0.0`,

    // Performance: capture 20% of transactions in production
    tracesSampleRate: 0.2,

    // Session replays: capture 10% of sessions, 100% on error
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,

    integrations: [
      Sentry.browserTracingIntegration(),
      Sentry.replayIntegration({
        // Mask all text and block all media for PII compliance (Kenya farmers)
        maskAllText: true,
        blockAllMedia: true,
      }),
    ],

    // Do not send events for auth errors — expected 401/403s from expired tokens
    beforeSend(event) {
      if (event.exception) {
        const values = event.exception.values ?? [];
        const isAuthError = values.some((ex) =>
          ex.value?.includes("401") || ex.value?.includes("403")
        );
        if (isAuthError) return null;
      }
      return event;
    },
  });
}

/**
 * Re-export the Sentry ErrorBoundary for use in the app tree.
 * Wrapping the root with this ensures unhandled React errors are captured.
 */
export { Sentry };
