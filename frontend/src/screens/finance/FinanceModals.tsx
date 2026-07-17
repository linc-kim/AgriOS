/**
 * Greena — Finance modals: log revenue and log expense.
 * Wired to the existing Finance API (expenses + revenue records).
 */
import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";

import { logExpense, logRevenue, listExpenseCategories } from "@/api/finance";
import { listFlocks } from "@/api/flocks";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select } from "@/components/ui/Select";
import type { ExpenseCreateInput, PaymentMethod, RevenueRecordCreateInput, RevenueType } from "@/types";

const TODAY = () => new Date().toISOString().slice(0, 10);
const errMsg = (e: any, fallback: string) => e?.response?.data?.error?.message ?? fallback;

const PAYMENT_METHODS = [
  { value: "cash", label: "Cash" },
  { value: "mpesa", label: "M-Pesa" },
  { value: "bank_transfer", label: "Bank transfer" },
  { value: "credit", label: "Credit (unpaid)" },
];

const REVENUE_TYPES = [
  { value: "eggs", label: "Egg sales" },
  { value: "birds", label: "Bird sales" },
  { value: "chicks", label: "Chick sales" },
  { value: "manure", label: "Manure sales" },
  { value: "other", label: "Other income" },
];

function ModalShell({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center sm:items-center" role="dialog" aria-modal>
      <div className="absolute inset-0 bg-gray-900/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative max-h-[90dvh] w-full max-w-md overflow-y-auto rounded-t-3xl border border-gray-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-[#161a20] sm:rounded-3xl">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-white/10">
            <X className="h-5 w-5" />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div role="alert" className="mb-4 rounded-xl border border-red-100 bg-red-50 px-3.5 py-2.5 text-sm text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300">
      {message}
    </div>
  );
}

// ── Log Revenue ───────────────────────────────────────────────────────────────

export function LogRevenueModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const flocksQuery = useQuery({ queryKey: ["flocks", farmId], queryFn: () => listFlocks(farmId) });
  const flocks = flocksQuery.data ?? [];

  const [f, setF] = useState({
    revenue_type: "eggs" as RevenueType,
    flock_id: "",
    amount: "",
    revenue_date: TODAY(),
    birds_sold: "",
    avg_weight_kg: "",
    eggs_count: "",
    trays_count: "",
    buyer_name: "",
    payment_method: "cash" as PaymentMethod,
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const input: RevenueRecordCreateInput = {
        flock_id: f.flock_id,
        revenue_type: f.revenue_type,
        revenue_date: f.revenue_date,
        amount: f.amount,
        buyer_name: f.buyer_name || undefined,
        payment_method: f.payment_method,
        birds_sold: f.revenue_type === "birds" && f.birds_sold ? Number(f.birds_sold) : undefined,
        avg_weight_kg: f.revenue_type === "birds" && f.avg_weight_kg ? f.avg_weight_kg : undefined,
        eggs_count: f.revenue_type === "eggs" && f.eggs_count ? Number(f.eggs_count) : undefined,
        trays_count: f.revenue_type === "eggs" && f.trays_count ? Number(f.trays_count) : undefined,
      };
      return logRevenue(farmId, input);
    },
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't save the revenue record.")),
  });

  const valid = f.flock_id && Number(f.amount) > 0 && f.revenue_date
    && (f.revenue_type !== "birds" || Number(f.birds_sold) > 0)
    && (f.revenue_type !== "eggs" || Number(f.eggs_count) > 0 || Number(f.trays_count) > 0);

  return (
    <ModalShell title="Record revenue" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="space-y-4">
        <Select label="Revenue type" options={REVENUE_TYPES} value={f.revenue_type} onChange={(e) => set({ revenue_type: e.target.value as RevenueType })} />
        <Select
          label="Flock"
          options={[{ value: "", label: flocksQuery.isLoading ? "Loading…" : "Select a flock" }, ...flocks.map((fl) => ({ value: fl.id, label: fl.name }))]}
          value={f.flock_id}
          onChange={(e) => set({ flock_id: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Amount (KES)" type="number" min={0} value={f.amount} onChange={(e) => set({ amount: e.target.value })} />
          <TextField label="Date" type="date" value={f.revenue_date} onChange={(e) => set({ revenue_date: e.target.value })} />
        </div>
        {f.revenue_type === "birds" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Birds sold" type="number" min={0} value={f.birds_sold} onChange={(e) => set({ birds_sold: e.target.value })} />
            <TextField label="Avg weight (kg)" type="number" min={0} value={f.avg_weight_kg} onChange={(e) => set({ avg_weight_kg: e.target.value })} />
          </div>
        )}
        {f.revenue_type === "eggs" && (
          <div className="grid grid-cols-2 gap-3">
            <TextField label="Eggs" type="number" min={0} value={f.eggs_count} onChange={(e) => set({ eggs_count: e.target.value })} />
            <TextField label="Trays" type="number" min={0} value={f.trays_count} onChange={(e) => set({ trays_count: e.target.value })} />
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Buyer (optional)" value={f.buyer_name} onChange={(e) => set({ buyer_name: e.target.value })} />
          <Select label="Payment" options={PAYMENT_METHODS} value={f.payment_method} onChange={(e) => set({ payment_method: e.target.value as PaymentMethod })} />
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Record</Button>
      </div>
    </ModalShell>
  );
}

// ── Log Expense ───────────────────────────────────────────────────────────────

export function LogExpenseModal({ farmId, onClose, onSaved }: { farmId: string; onClose: () => void; onSaved: () => void }) {
  const catsQuery = useQuery({ queryKey: ["expense-categories", farmId], queryFn: () => listExpenseCategories(farmId) });
  const flocksQuery = useQuery({ queryKey: ["flocks", farmId], queryFn: () => listFlocks(farmId) });
  const cats = catsQuery.data ?? [];
  const flocks = flocksQuery.data ?? [];

  const [f, setF] = useState({
    category_id: "",
    amount: "",
    expense_date: TODAY(),
    description: "",
    flock_id: "",
    supplier: "",
    payment_method: "cash" as PaymentMethod,
  });
  const set = (p: Partial<typeof f>) => setF((s) => ({ ...s, ...p }));
  const [error, setError] = useState<string | null>(null);

  const save = useMutation({
    mutationFn: () => {
      const input: ExpenseCreateInput = {
        category_id: f.category_id,
        expense_date: f.expense_date,
        amount: f.amount,
        description: f.description.trim(),
        payment_method: f.payment_method,
        flock_id: f.flock_id || undefined,
        supplier: f.supplier || undefined,
      };
      return logExpense(farmId, input);
    },
    onSuccess: onSaved,
    onError: (e) => setError(errMsg(e, "Couldn't save the expense.")),
  });

  const valid = f.category_id && Number(f.amount) > 0 && f.description.trim().length >= 2 && f.expense_date;

  return (
    <ModalShell title="Record expense" onClose={onClose}>
      <ErrorBanner message={error} />
      <div className="space-y-4">
        <Select
          label="Category"
          options={[{ value: "", label: catsQuery.isLoading ? "Loading…" : "Select a category" }, ...cats.map((c) => ({ value: c.id, label: `${c.icon ?? ""} ${c.name}`.trim() }))]}
          value={f.category_id}
          onChange={(e) => set({ category_id: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Amount (KES)" type="number" min={0} value={f.amount} onChange={(e) => set({ amount: e.target.value })} />
          <TextField label="Date" type="date" value={f.expense_date} onChange={(e) => set({ expense_date: e.target.value })} />
        </div>
        <TextField label="Description" placeholder="e.g. 3 bags layer mash" value={f.description} onChange={(e) => set({ description: e.target.value })} />
        <Select
          label="Flock (optional)"
          options={[{ value: "", label: "Farm-wide" }, ...flocks.map((fl) => ({ value: fl.id, label: fl.name }))]}
          value={f.flock_id}
          onChange={(e) => set({ flock_id: e.target.value })}
        />
        <div className="grid grid-cols-2 gap-3">
          <TextField label="Supplier (optional)" value={f.supplier} onChange={(e) => set({ supplier: e.target.value })} />
          <Select label="Payment" options={PAYMENT_METHODS} value={f.payment_method} onChange={(e) => set({ payment_method: e.target.value as PaymentMethod })} />
        </div>
      </div>
      <div className="mt-6 flex gap-3">
        <Button variant="secondary" fullWidth onClick={onClose}>Cancel</Button>
        <Button fullWidth disabled={!valid} loading={save.isPending} onClick={() => { setError(null); save.mutate(); }}>Record</Button>
      </div>
    </ModalShell>
  );
}
