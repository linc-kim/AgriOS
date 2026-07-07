/**
 * Greena — Authentication layout.
 * A calm, premium split: a branded green panel (desktop) beside the form.
 */
import { Outlet } from "react-router-dom";
import { Logo } from "@/components/ui/Logo";

export default function AuthLayout() {
  return (
    <div className="min-h-[100dvh] w-full bg-white lg:grid lg:grid-cols-[1.05fr_1fr]">
      {/* Brand panel — desktop only */}
      <aside className="relative hidden overflow-hidden bg-brand-800 lg:flex lg:flex-col lg:justify-between lg:p-12">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0"
          style={{
            background:
              "radial-gradient(120% 90% at 15% 10%, #0a7a2c 0%, #065720 45%, #033c14 100%)",
          }}
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-24 -top-24 h-[420px] w-[420px] rounded-full opacity-[0.10] blur-2xl"
          style={{ background: "radial-gradient(circle, #66b701 0%, transparent 70%)" }}
        />
        <div className="relative">
          <Logo variant="lockup" tone="white" className="h-9 w-auto" />
        </div>

        <div className="relative max-w-md">
          <h1 className="text-[2.6rem] font-semibold leading-[1.08] tracking-[-0.02em] text-white">
            The operating system for your farm.
          </h1>
          <p className="mt-5 text-[15px] leading-relaxed text-white/70">
            Livestock, crops, finance, and intelligence — one calm, connected
            workspace. Set up your organization and first farm in under a minute.
          </p>
        </div>

        <div className="relative flex items-center gap-2 text-[13px] text-white/55">
          <span className="h-1.5 w-1.5 rounded-full bg-brand-300" />
          <span>Trusted farm operations, built for the field.</span>
        </div>
      </aside>

      {/* Form panel */}
      <main className="flex min-h-[100dvh] flex-col items-center justify-center px-5 py-10 sm:px-8">
        <div className="w-full max-w-[380px]">
          {/* Mobile logo (brand panel hidden) */}
          <div className="mb-8 lg:hidden">
            <Logo variant="lockup" className="h-9 w-auto" />
          </div>
          <Outlet />
        </div>
      </main>
    </div>
  );
}
