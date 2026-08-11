// Gate 5 — file-upload + concurrent-import workload. Sends multipart CSV imports to
// /data/imports with dry_run=true (validates the upload guard + parse path WITHOUT
// mutating data). Confirm valid `entity` names via GET /farms/{id}/data/imports/
// entities before a full run. Image (multimodal) uploads additionally need a real
// PNG fixture + a staging Gemini key — see the plan doc; kept out here to avoid a
// binary fixture in the repo.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE, pickUser } from './lib/common.js';

export const options = {
  scenarios: {
    uploads: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m', target: 50 },
        { duration: '5m', target: 200 }, // concurrent imports
        { duration: '1m', target: 0 },
      ],
    },
  },
  thresholds: { http_req_failed: ['rate<0.02'] },
};

const CSV = 'expense_date,amount,category\n2026-01-01,120.50,Feed\n2026-01-02,80,Vaccines\n';

export default function () {
  const u = pickUser();
  const f = u.farm_id;
  const res = http.post(
    `${BASE}/farms/${f}/data/imports?entity=expenses&dry_run=true`,
    { file: http.file(CSV, 'load.csv', 'text/csv') },
    { headers: { Authorization: `Bearer ${u.token}` }, tags: { kind: 'noai', name: 'import' } },
  );
  check(res, { 'status < 500': (x) => x.status < 500 });
  sleep(Math.random() * 2 + 1);
}
