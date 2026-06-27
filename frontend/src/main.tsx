/**
 * AGRIOS — Application Entry Point
 * Sprint 10: Sentry initialised before React renders.
 */

import "./index.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { ReactQueryDevtools } from "@tanstack/react-query-devtools";
import { queryClient } from "@/lib/queryClient";
import { AppRouter } from "@/routes";
import { ConnectivityWatcher } from "@/components/common/ConnectivityWatcher";
import { initialiseSentry, Sentry } from "@/lib/sentry";

// Must run before createRoot so bootstrap errors are captured
initialiseSentry();

const rootElement = document.getElementById("root");
if (!rootElement) throw new Error("Root element not found");

createRoot(rootElement).render(
  <StrictMode>
    <Sentry.ErrorBoundary
      fallback={({ error, resetError }) => (
        <div
          role="alert"
          style={{
            minHeight: "100vh",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            padding: "24px",
            background: "#f9fafb",
            fontFamily: "sans-serif",
          }}
        >
          <p style={{ fontSize: "2rem", marginBottom: "8px" }}>⚠️</p>
          <h1 style={{ fontSize: "1.125rem", fontWeight: 600, marginBottom: "8px", color: "#111827" }}>
            Something went wrong
          </h1>
          <p style={{ fontSize: "0.875rem", color: "#6b7280", marginBottom: "24px", textAlign: "center" }}>
            {error instanceof Error ? error.message : "An unexpected error occurred"}
          </p>
          <button
            onClick={resetError}
            style={{
              padding: "10px 20px",
              background: "#16a34a",
              color: "#fff",
              border: "none",
              borderRadius: "8px",
              fontSize: "0.875rem",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Try again
          </button>
        </div>
      )}
    >
      <QueryClientProvider client={queryClient}>
        <AppRouter />
        <ConnectivityWatcher />
        {import.meta.env.DEV && <ReactQueryDevtools position="bottom-right" />}
      </QueryClientProvider>
    </Sentry.ErrorBoundary>
  </StrictMode>,
);
