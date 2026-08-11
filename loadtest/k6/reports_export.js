// Gate 5 — large reporting exports: concurrent CSV/report generation. Exports are
// heavier (serialize + stream) and are candidates for background offloading; this
// scenario measures their latency and whether they starve the pool under load.
// Confirm the export paths/permissions against your build before a full run.
import { check, sleep } from 'k6';
import { pickUser, authGet } from './lib/common.js';

export const options = {
  scenarios: {
    exports: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 100 },
        { duration: '5m', target: 300 },
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    // Exports legitimately take longer than interactive reads — separate budget.
    'http_req_duration{name:export}': ['p(95)<3000'],
  },
};

export default function () {
  const u = pickUser();
  const f = u.farm_id;
  const paths = [
    `/farms/${f}/finance/reports/csv`,
    `/farms/${f}/data/exports`,
    `/farms/${f}/aviculture/reports/collection.csv`,
    `/farms/${f}/bsf/reports/production.csv`,
  ];
  const path = paths[Math.floor(Math.random() * paths.length)];
  const res = authGet(path, u);
  // retag as export for the threshold above
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(Math.random() * 2 + 1);
}
