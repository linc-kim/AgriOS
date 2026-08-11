// Gate 5 — AI-heavy workload: concentrates traffic on the AI surface (chat,
// dashboard, ARIA insights) to find provider-throughput and cost/cache behaviour.
// AI calls are tagged `kind:ai` so they're excluded from the non-AI latency SLO but
// still counted for errors. Enable a STAGING Gemini key + the response cache to see
// hit-ratio and rotation under load (GET /admin/ai/health).
import { check, sleep } from 'k6';
import { pickUser, authGet, authPost } from './lib/common.js';

export const options = {
  scenarios: {
    ai_heavy: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 100 },
        { duration: '2m', target: 400 },
        { duration: '10m', target: 400 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.02'], // AI is provider-bound; allow a wider error budget
  },
};

export default function () {
  const u = pickUser();
  const f = u.farm_id;
  const r = Math.random();
  let res;
  if (r < 0.45) res = authPost(`/farms/${f}/ai/ask`, { question: 'How is my flock and what should I do today?' }, u, 'ai');
  else if (r < 0.75) res = authGet(`/farms/${f}/ai/dashboard`, u, 'ai');
  else res = authGet(`/farms/${f}/aria/insights`, u, 'ai');
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(Math.random() * 1.5 + 0.5);
}
