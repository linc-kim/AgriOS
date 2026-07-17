/**
 * Greena — Finance charts (Recharts). Theme-aware, responsive.
 */
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { FinCashflowPoint, FinCategoryAmount, FinMoneyPoint } from "@/types";

const kesTip = (v: any) => `KES ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
const axis = { fontSize: 11, fill: "#94a3b8" };
const tipStyle = { borderRadius: 12, border: "1px solid rgba(148,163,184,0.3)", fontSize: 12 };
const grid = "rgba(148,163,184,0.2)";

export function RevenueExpenseChart({ data }: { data: FinMoneyPoint[] }) {
  const rows = data.map((p) => ({
    period: p.period.slice(5),
    Revenue: Number(p.revenue),
    Expenses: Number(p.expenses),
  }));
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} />
          <XAxis dataKey="period" tick={axis} interval="preserveStartEnd" />
          <YAxis tick={axis} />
          <Tooltip contentStyle={tipStyle} formatter={kesTip} />
          <Bar dataKey="Revenue" fill="#16a34a" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Expenses" fill="#ef4444" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function ProfitTrendChart({ data }: { data: FinMoneyPoint[] }) {
  const rows = data.map((p) => ({ period: p.period.slice(5), Profit: Number(p.profit) }));
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={rows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <defs>
            <linearGradient id="profitGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#16a34a" stopOpacity={0.4} />
              <stop offset="95%" stopColor="#16a34a" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} />
          <XAxis dataKey="period" tick={axis} interval="preserveStartEnd" />
          <YAxis tick={axis} />
          <Tooltip contentStyle={tipStyle} formatter={kesTip} />
          <Area type="monotone" dataKey="Profit" stroke="#16a34a" fill="url(#profitGrad)" strokeWidth={2} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CategoryChart({ data }: { data: FinCategoryAmount[] }) {
  const rows = data.slice(0, 8).map((c) => ({ name: c.name, amount: Number(c.amount), color: c.color ?? "#64748b" }));
  return (
    <div className="h-56">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={rows} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} horizontal={false} />
          <XAxis type="number" tick={axis} />
          <YAxis type="category" dataKey="name" tick={{ ...axis, fontSize: 10 }} width={96} />
          <Tooltip contentStyle={tipStyle} formatter={kesTip} />
          <Bar dataKey="amount" radius={[0, 4, 4, 0]}>
            {rows.map((r, i) => <Cell key={i} fill={r.color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CashflowChart({ data }: { data: FinCashflowPoint[] }) {
  const rows = data.map((p) => ({
    period: p.period.slice(2),
    Inflow: Number(p.inflow),
    Outflow: -Number(p.outflow),
    Balance: Number(p.running_balance),
  }));
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={rows} margin={{ top: 4, right: 8, left: -12, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={grid} />
          <XAxis dataKey="period" tick={axis} />
          <YAxis tick={axis} />
          <Tooltip contentStyle={tipStyle} formatter={(v: any) => kesTip(Math.abs(Number(v)))} />
          <Bar dataKey="Inflow" fill="#16a34a" radius={[4, 4, 0, 0]} />
          <Bar dataKey="Outflow" fill="#ef4444" radius={[0, 0, 4, 4]} />
          <Line type="monotone" dataKey="Balance" stroke="#0ea5e9" strokeWidth={2} dot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
