import { Link } from "react-router-dom";
import {
  Building2,
  Sprout,
  MapPin,
  Bird,
  Wallet,
  Sparkles,
  ArrowRight,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { useWorkspace } from "@/shell/useWorkspace";
import { useAuthStore } from "@/stores/authStore";
import { Skeleton } from "@/components/ui/Skeleton";
import { EmptyState } from "@/components/ui/EmptyState";

function StatCard({
  icon: Icon,
  label,
  value,
  sub,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
  sub?: string;
}) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center gap-2 text-gray-400">
        <Icon className="h-4 w-4" />
        <span className="text-xs font-semibold uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-3 truncate text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">
        {value}
      </p>
      {sub && <p className="mt-0.5 truncate text-sm text-gray-500 dark:text-gray-400">{sub}</p>}
    </div>
  );
}

function ActionCard({
  to,
  icon: Icon,
  title,
  desc,
}: {
  to: string;
  icon: LucideIcon;
  title: string;
  desc: string;
}) {
  return (
    <Link
      to={to}
      className="group flex items-center gap-4 rounded-2xl border border-gray-200 bg-white p-4 transition-all hover:border-brand-200 hover:shadow-sm dark:border-white/10 dark:bg-white/[0.03] dark:hover:border-brand-600/40"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600 dark:bg-brand-600/15 dark:text-brand-300">
        <Icon className="h-5 w-5" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-sm font-semibold text-gray-900 dark:text-white">{title}</span>
        <span className="block truncate text-sm text-gray-500 dark:text-gray-400">{desc}</span>
      </span>
      <ArrowRight className="h-4 w-4 text-gray-300 transition-transform group-hover:translate-x-0.5 group-hover:text-brand-500" />
    </Link>
  );
}

function DashboardSkeleton() {
  return (
    <div className="space-y-7">
      <Skeleton className="h-8 w-64" />
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-28 rounded-2xl" />
        ))}
      </div>
      <Skeleton className="h-40 rounded-2xl" />
    </div>
  );
}

export default function DashboardScreen() {
  const user = useAuthStore((s) => s.user);
  const { currentOrg, currentFarm, farms, isLoading } = useWorkspace();
  const firstName = user?.full_name?.split(" ")[0];

  if (isLoading) return <DashboardSkeleton />;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-2xl font-semibold tracking-[-0.02em] text-gray-900 dark:text-white">
          Good to see you{firstName ? `, ${firstName}` : ""}
        </h1>
        <p className="mt-1 text-[15px] text-gray-500 dark:text-gray-400">
          Here's what's happening at{" "}
          <span className="font-medium text-gray-700 dark:text-gray-200">
            {currentFarm?.name ?? currentOrg?.name ?? "your farm"}
          </span>
          .
        </p>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard
          icon={Building2}
          label="Organization"
          value={currentOrg?.name ?? "—"}
          sub={currentOrg ? `${currentOrg.currency} · ${currentOrg.country ?? "—"}` : undefined}
        />
        <StatCard icon={Sprout} label="Farms" value={String(farms.length)} sub="in this workspace" />
        <StatCard
          icon={MapPin}
          label="Current farm"
          value={currentFarm?.name ?? "—"}
          sub={currentFarm?.location ?? currentFarm?.county ?? "Set a location"}
        />
      </div>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Quick actions</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <ActionCard to="/livestock" icon={Bird} title="Add livestock" desc="Start tracking a flock" />
          <ActionCard to="/finance" icon={Wallet} title="Record finances" desc="Log an expense or sale" />
          <ActionCard to="/ai" icon={Sparkles} title="Ask Greena" desc="Get farm guidance" />
        </div>
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-gray-900 dark:text-white">Recent activity</h2>
        <EmptyState
          icon={<Sprout className="h-6 w-6" />}
          title="Nothing to show yet"
          description="As you run your farm — logging production, finances, and health — the latest activity will appear here."
        />
      </section>
    </div>
  );
}
