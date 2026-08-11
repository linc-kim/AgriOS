// Shared helpers for the Gate 5 k6 scenarios.
// Tokens come from loadtest/data/tokens.json (produced by loadtest/seed_staging.py):
//   [{ "email": "...", "password": "...", "farm_id": "uuid", "token": "jwt" }, ...]
import http from 'k6/http';
import { SharedArray } from 'k6/data';

export const BASE = (__ENV.BASE_URL || 'http://localhost:8000') + '/api/v1';

// Loaded once per VU pool, shared across VUs (memory-efficient).
export const users = new SharedArray('users', function () {
  const path = __ENV.TOKENS || '../data/tokens.json';
  return JSON.parse(open(path));
});

export function pickUser() {
  return users[Math.floor(Math.random() * users.length)];
}

// `kind` tags requests so thresholds can hold non-AI endpoints to the SLO while
// excluding provider-bound AI calls from the latency target (still counted for errors).
export function authGet(path, u, kind) {
  return http.get(`${BASE}${path}`, {
    headers: { Authorization: `Bearer ${u.token}` },
    tags: { kind: kind || 'noai', name: path.replace(/[0-9a-f-]{36}/g, '{id}') },
  });
}

export function authPost(path, body, u, kind) {
  return http.post(`${BASE}${path}`, JSON.stringify(body), {
    headers: { Authorization: `Bearer ${u.token}`, 'Content-Type': 'application/json' },
    tags: { kind: kind || 'noai', name: path.replace(/[0-9a-f-]{36}/g, '{id}') },
  });
}

// Non-AI SLO thresholds shared by the scenarios (Gate 5 success criteria).
export const NOAI_THRESHOLDS = {
  http_req_failed: ['rate<0.005'],
  'http_req_duration{kind:noai}': ['p(95)<500', 'p(99)<1000'],
};
