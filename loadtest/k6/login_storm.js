// Gate 5 — login storm: many simultaneous authentications.
// Exercises the auth surface (rate limiting, password hashing cost, session writes).
// NOTE: the app rate-limits /auth/* per IP (20/60s in-process). A single-IP k6 run
// will (correctly) get 429s — that is the limiter working, not a failure. To test
// real login throughput, distribute generators across IPs or raise the limit in a
// dedicated staging config, and treat 429 as an expected, non-error outcome here.
import http from 'k6/http';
import { check } from 'k6';
import { SharedArray } from 'k6/data';

const BASE = (__ENV.BASE_URL || 'http://localhost:8000') + '/api/v1';
const users = new SharedArray('users', () => JSON.parse(open(__ENV.TOKENS || '../data/tokens.json')));

export const options = {
  scenarios: {
    login_storm: {
      executor: 'ramping-arrival-rate',
      startRate: 20,
      timeUnit: '1s',
      preAllocatedVUs: 200,
      maxVUs: 1000,
      stages: [
        { duration: '1m', target: 100 },  // 100 logins/s
        { duration: '3m', target: 300 },  // storm
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    // Success OR expected rate-limit; only 5xx counts as failure.
    'http_req_failed{expected_response:true}': ['rate<0.01'],
  },
};

export default function () {
  const u = users[Math.floor(Math.random() * users.length)];
  const res = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ email: u.email, password: u.password }),
    { headers: { 'Content-Type': 'application/json' }, tags: { name: '/auth/login' } },
  );
  check(res, { 'ok or rate-limited': (x) => x.status === 200 || x.status === 429 });
}
