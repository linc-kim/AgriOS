// Gate 5 — dashboard refresh storm: many clients refreshing dashboards at once
// (the heaviest read path — baseline showed ai:dashboard=70q, finance analytics=39q).
// This is the scenario most likely to expose connection-pool pressure and the
// serial-aggregation bottlenecks flagged in the Phase 1 baseline.
import { check, sleep } from 'k6';
import { pickUser, authGet, NOAI_THRESHOLDS } from './lib/common.js';

export const options = {
  scenarios: {
    storm: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 400,
      maxVUs: 1500,
      stages: [
        { duration: '1m', target: 200 },
        { duration: '3m', target: 800 },   // 800 dashboard refreshes/s
        { duration: '2m', target: 800 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: NOAI_THRESHOLDS,
};

export default function () {
  const u = pickUser();
  const f = u.farm_id;
  const paths = [
    `/farms/${f}/production-dashboard`,
    `/farms/${f}/finance/overview`,
    `/farms/${f}/finance/analytics`,
    `/farms/${f}/health/summary`,
  ];
  const res = authGet(paths[Math.floor(Math.random() * paths.length)], u);
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(0.3);
}
