// Gate 5 — burst: sudden spike then drop, to test whether the platform absorbs a
// surge and recovers (rather than cascading into 5xx). Uses arrival-rate so the
// spike is request-driven regardless of response time.
//
// Run:  BASE_URL=... k6 run burst.js
import { check, sleep } from 'k6';
import { pickUser, authGet, NOAI_THRESHOLDS } from './lib/common.js';

export const options = {
  scenarios: {
    burst: {
      executor: 'ramping-arrival-rate',
      startRate: 50,
      timeUnit: '1s',
      preAllocatedVUs: 300,
      maxVUs: 1500,
      stages: [
        { duration: '30s', target: 50 },    // steady
        { duration: '15s', target: 1200 },  // sudden spike
        { duration: '1m', target: 1200 },   // hold the spike
        { duration: '15s', target: 50 },    // drop
        { duration: '1m', target: 50 },     // observe recovery
      ],
    },
  },
  thresholds: NOAI_THRESHOLDS,
};

export default function () {
  const u = pickUser();
  const res = authGet(`/farms/${u.farm_id}/production-dashboard`, u);
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(0.2);
}
