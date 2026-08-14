# Greena V1 LC1 — Install-to-Home-Screen (App-Like Experience)

**Date:** 2026-08-14 · **Branch:** `phase-2-auth` · **Commit:** `7a2aaea`

## Inspection (before changing anything)
Greena was **already PWA-capable** — this was refinement, not new plumbing.

| Item | Found |
|---|---|
| Manifest | Yes — via `vite-plugin-pwa` in `vite.config.ts` (name "Greena — Farm Operating System", short_name "Greena", `display: standalone`, `theme_color #076524`, `background #ffffff`, portrait, start_url `/`) |
| Service worker | Yes — `registerType: autoUpdate`, generated `sw.js` (precache ~269 entries) |
| Icons | Full set in `public/icons/` incl. `maskable-512.png`, `apple-touch-icon.png`, `android-chrome-*` |
| Existing PWA UI | `OfflineBanner`, `PWAUpdatePrompt` |
| Install prompt / guide | **None** — no `beforeinstallprompt` handling, no install UI |

**Issues fixed:** (1) workbox `runtimeCaching` targeted a non-existent `api.agrios.app` host with StaleWhileRevalidate — dead config that, if repointed at the live API, would serve stale farm/financial/auth data; **removed** (static precache kept). (2) `maskable-512.png` existed but was unused — manifest reused `icon-512` as "any maskable" (clips on Android); now split into dedicated `any` + `maskable`. (3) Description broadened beyond "poultry".

## Implementation
| Piece | File | Notes |
|---|---|---|
| Install state hook | `src/hooks/usePwaInstall.ts` | Captures `beforeinstallprompt`; detects Android / iOS / iPadOS / desktop; detects standalone (display-mode + `navigator.standalone`); `appinstalled` handling; `promptInstall()` |
| Install guide | `src/screens/public/InstallScreen.tsx` (`/install`) | Auto-selects platform, manual Android / iPhone-iPad / Computer switch, native one-tap install when available, numbered steps, plain language (no jargon), installed-state reassurance, "not in Play/App Store" honesty |
| Entry points | Footer ("Put Greena on your phone"), Help FAQ (2 entries) | Non-spammy; no recurring banner |
| Manifest/SW | `vite.config.ts` | See fixes above |

Language avoids "PWA/manifest/service worker/standalone". iPhone path explicitly Safari; Android wording hedged ("if you see Install app, tap it; otherwise Add to Home screen").

## Verification — Environment → Test → Result → Evidence
| Environment | Test | Result | Evidence |
|---|---|---|---|
| Local build | `vite build` | **PASS** | Built 30.4s; `manifest.webmanifest` regenerated; `sw.js` 272 precache entries; no errors |
| Local build | Manifest icons | **PASS** | `icon-48..512` `purpose:any`; `maskable-512.png` `purpose:maskable`; broadened description |
| Local typecheck | `tsc --noEmit` on changed files | **PASS** | 0 errors in new/changed files (2 pre-existing `rabbit/` errors unrelated) |
| Dev browser (desktop UA) | Render `/install` | **PASS** | Title "Put Greena on your phone · Greena"; auto-selected **Computer**; no console errors |
| Dev browser | Device switch → Android | **PASS** | Steps swapped to Chrome-menu → Install app flow |
| Dev browser (375px, Android UA) | Auto-detect + responsive | **PASS** | Auto-selected **Android**; layout responsive |
| — | Installed/standalone runtime | **UNVERIFIED** | Logic implemented + code-reviewed; cannot emulate a true home-screen (standalone) launch in the test browser |
| Production | Any of the above from prod URL | **BLOCKED** | Vercel deployment protection (SSO) gates the public site; not deployed yet |

## Farmer-readiness check
A farmer can open `/install`, see the steps for their exact device (or a one-tap Install button on Chrome), follow See → Tap → See → Tap → Done, and get a Greena icon — with no mention of web-app internals. **Met at the code/local level; production + real-device confirmation pending deploy.**

## Remaining
- **BLOCKED (owner):** deploy + production verification gated by Vercel SSO protection.
- **UNVERIFIED:** real-device Android install + iOS Add-to-Home-Screen + standalone launch (needs a physical device against a reachable deployment).
- **Optional:** an in-app (authenticated) install hint in onboarding/dashboard — not added, to avoid clutter.
