// Gate 5 — sustained mixed workload across all Greena modules.
// Ramps to 1,000 VUs and holds ~20 min. Traffic is weighted like real farmer use
// (mostly reads; a small share of writes and AI). Reads are known-safe; the write
// and AI calls should be smoke-tested against your API build first (payload shapes
// can change) so they don't inflate the error rate.
//
// Run:  BASE_URL=http://localhost:8000 TOKENS=../data/tokens.json k6 run mixed_workload.js
import { check, sleep } from 'k6';
import { pickUser, authGet, authPost, NOAI_THRESHOLDS } from './lib/common.js';

export const options = {
  scenarios: {
    mixed: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '2m', target: 250 },   // warm up
        { duration: '3m', target: 1000 },  // ramp to target
        { duration: '20m', target: 1000 }, // sustain (15–30 min)
        { duration: '2m', target: 0 },     // ramp down (observe recovery)
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: NOAI_THRESHOLDS,
};

export default function () {
  const u = pickUser();
  const f = u.farm_id;
  const r = Math.random();
  let res;

  if (r < 0.28) res = authGet(`/farms/${f}`, u);
  else if (r < 0.48) res = authGet(`/farms/${f}/production-dashboard`, u);
  else if (r < 0.60) res = authGet(`/farms/${f}/flocks`, u);
  else if (r < 0.70) res = authGet(`/farms/${f}/finance/overview`, u);
  else if (r < 0.78) res = authGet(`/farms/${f}/health/summary`, u);
  else if (r < 0.84) res = authGet(`/farms/${f}/automation/reminders`, u);
  else if (r < 0.90) res = authGet(`/farms/${f}/ai/dashboard`, u); // heavy (baseline: 70 queries)
  else if (r < 0.96)
    res = authPost(`/farms/${f}/finance/categories`, { name: `Load ${Date.now()}`, kind: 'expense' }, u);
  else
    res = authPost(`/farms/${f}/ai/ask`, { question: 'How is my flock doing?' }, u, 'ai');

  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(Math.random() * 2 + 0.5); // think time 0.5–2.5s
}
