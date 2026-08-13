import { test, expect, request as pwRequest, type APIRequestContext } from "@playwright/test";

// Production backend API base (override via env).
const API = process.env.E2E_API ?? "https://greena-api-v91z.onrender.com/api/v1";
const PASSWORD = "GreenaTest123!";
const STARTER = "00000000-0000-0000-0000-000000000002";
const stamp = () => `${Date.now()}${Math.floor(Math.random() * 1000)}`;

async function signup(api: APIRequestContext, label: string) {
  const email = `greena-e2e-${label}-${stamp()}@example.com`;
  const r = await api.post(`${API}/auth/signup`, {
    data: { email, password: PASSWORD, full_name: `E2E ${label}` },
  });
  expect(r.status(), "signup 201").toBe(201);
  const token = (await r.json()).data.access_token as string;
  return { email, token, auth: { Authorization: `Bearer ${token}` } };
}

async function createOrg(api: APIRequestContext, auth: Record<string, string>) {
  const r = await api.post(`${API}/organizations`, {
    headers: auth,
    data: { name: `E2E Farm ${stamp()}`, country: "KE", timezone: "Africa/Nairobi", currency: "KES" },
  });
  expect(r.status(), "org 201").toBe(201);
  return (await r.json()).data.id as string;
}

// ─────────────────────────────────────────────────────────────────────────────
// 1 · UI smoke — the deployed Vercel frontend renders and reaches the backend.
// ─────────────────────────────────────────────────────────────────────────────
test.describe("UI @production", () => {
  test("login screen renders with email + password fields", async ({ page }) => {
    const resp = await page.goto("/login", { waitUntil: "domcontentloaded" });
    expect(resp?.status(), "frontend served").toBeLessThan(400);
    await expect(page.getByText("Welcome back")).toBeVisible();
    await expect(page.locator('input[type="email"]')).toBeVisible();
    await expect(page.locator('input[type="password"]')).toBeVisible();
    await expect(page.getByRole("button", { name: /log in/i })).toBeVisible();
  });

  test("unauthenticated app redirects to /login", async ({ page }) => {
    await page.goto("/", { waitUntil: "domcontentloaded" });
    await expect(page).toHaveURL(/\/login/);
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 2 · Full journey against the deployed backend (real writes to production).
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Journey @production", () => {
  let api: APIRequestContext;
  test.beforeAll(async () => { api = await pwRequest.newContext(); });
  test.afterAll(async () => { await api.dispose(); });

  test("signup → me (auto-verified in prod auth mode)", async () => {
    const { email, auth } = await signup(api, "me");
    const r = await api.get(`${API}/auth/me`, { headers: auth });
    expect(r.status()).toBe(200);
    const u = (await r.json()).data;
    expect(u.email).toBe(email);
  });

  test("org creation grants 21-day trial + referral code", async () => {
    const { auth } = await signup(api, "org");
    const oid = await createOrg(api, auth);

    const trial = await api.get(`${API}/billing/trial/${oid}`, { headers: auth });
    expect(trial.status()).toBe(200);
    const td = (await trial.json()).data;
    expect(td.is_trial).toBe(true);
    expect(td.days_remaining).toBeGreaterThan(15);

    const ref = await api.get(`${API}/billing/referral/${oid}`, { headers: auth });
    expect(ref.status()).toBe(200);
    expect((await ref.json()).data.referral_code).toMatch(/^GREENA-/);
  });

  test("farm creation persists", async () => {
    const { auth } = await signup(api, "farm");
    const oid = await createOrg(api, auth);
    const create = await api.post(`${API}/farms`, {
      headers: auth,
      data: { name: "E2E Poultry", county: "Nairobi", location: "Karen", organization_id: oid },
    });
    expect(create.status()).toBe(201);
    const list = await api.get(`${API}/farms`, { headers: auth });
    expect(list.status()).toBe(200);
    expect((await list.json()).data.length).toBeGreaterThanOrEqual(1);
  });

  test("referral applies the first-payment discount (599 vs 999)", async () => {
    const referrer = await signup(api, "refA");
    const rOrg = await createOrg(api, referrer.auth);
    const code = (await (await api.get(`${API}/billing/referral/${rOrg}`, { headers: referrer.auth })).json())
      .data.referral_code as string;

    const referred = await signup(api, "refB");
    const bOrg = await createOrg(api, referred.auth);
    const submit = await api.post(`${API}/billing/referral/${bOrg}`, { headers: referred.auth, data: { code } });
    expect(submit.status()).toBe(201);

    const init = await api.post(`${API}/billing/initialize`, {
      headers: referred.auth,
      data: { organization_id: bOrg, plan_id: STARTER, callback_url: "https://agrioskenya.vercel.app/billing/callback" },
    });
    expect(init.status()).toBe(201);
    const d = (await init.json()).data;
    expect(d.amount_kes ?? d.amount).toBe(599);
    expect(d.authorization_url).toContain("paystack.com");
  });

  test("checkout initialization returns a Paystack authorization URL", async () => {
    const { auth } = await signup(api, "pay");
    const oid = await createOrg(api, auth);
    const init = await api.post(`${API}/billing/initialize`, {
      headers: auth,
      data: { organization_id: oid, plan_id: STARTER },
    });
    expect(init.status()).toBe(201);
    expect((await init.json()).data.authorization_url).toContain("checkout.paystack.com");
  });
});

// ─────────────────────────────────────────────────────────────────────────────
// 3 · Security assertions against the deployed backend.
// ─────────────────────────────────────────────────────────────────────────────
test.describe("Security @production", () => {
  let api: APIRequestContext;
  test.beforeAll(async () => { api = await pwRequest.newContext(); });
  test.afterAll(async () => { await api.dispose(); });

  test("protected route without a token → 401", async () => {
    expect((await api.get(`${API}/farms`)).status()).toBe(401);
  });

  test("tenant isolation — outsider cannot read another org → 404", async () => {
    const owner = await signup(api, "own");
    const oid = await createOrg(api, owner.auth);
    const outsider = await signup(api, "out");
    for (const path of [`billing/trial/${oid}`, `billing/referral/${oid}`]) {
      expect((await api.get(`${API}/${path}`, { headers: outsider.auth })).status()).toBe(404);
    }
  });

  test("webhook rejects an invalid signature → 401", async () => {
    const r = await api.post(`${API}/billing/webhook`, {
      headers: { "x-paystack-signature": "invalid" },
      data: { event: "charge.success", data: { reference: "greena_x" } },
    });
    expect(r.status()).toBe(401);
  });
});
