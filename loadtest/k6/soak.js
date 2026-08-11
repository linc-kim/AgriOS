// Gate 5 — soak: steady moderate load for 12–24 h to surface memory / connection
// leaks and slow degradation. Watch RSS and pg_stat_activity for monotonic growth
// while this runs (see docs/GATE_5_LOADTEST_PLAN.md §5–6).
//
// Run:  BASE_URL=... SOAK_HOURS=12 k6 run soak.js
import { sleep, check } from 'k6';
import { pickUser, authGet, NOAI_THRESHOLDS } from './lib/common.js';

const HOURS = __ENV.SOAK_HOURS || '12';

export const options = {
  scenarios: {
    soak: {
      executor: 'constant-vus',
      vus: Number(__ENV.SOAK_VUS || 150),
      duration: `${HOURS}h`,
    },
  },
  thresholds: NOAI_THRESHOLDS,
};

export default function () {
  const u = pickUser();
  const f = u.farm_id;
  const paths = [`/farms/${f}`, `/farms/${f}/production-dashboard`, `/farms/${f}/flocks`,
    `/farms/${f}/finance/overview`, `/farms/${f}/health/summary`];
  const res = authGet(paths[Math.floor(Math.random() * paths.length)], u);
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(Math.random() * 3 + 1);
}
