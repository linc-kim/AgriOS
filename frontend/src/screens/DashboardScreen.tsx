/**
 * AGRIOS Screen F-01 — Dashboard
 * Sprint 0: Placeholder that confirms auth is working.
 * Sprint 7: Fully wired with all 6 data zones.
 */

import { useAuthStore } from "@/stores/authStore";

export default function DashboardScreen() {
  const { user } = useAuthStore();

  return (
    <div className="p-4 space-y-4">
      {/* Welcome */}
      <div className="bg-white rounded-2xl p-4 border border-gray-100">
        <h2 className="text-xl font-bold text-gray-900">
          Welcome, {user?.full_name ?? "Farmer"} 👋
        </h2>
        <p className="text-gray-500 text-sm mt-1">
          AGRIOS is running. Sprint 1 begins now.
        </p>
      </div>

      {/* Sprint progress indicator */}
      <div className="bg-brand-50 rounded-2xl p-4 border border-brand-100">
        <h3 className="text-sm font-semibold text-brand-800">
          Sprint 0 Complete
        </h3>
        <p className="text-brand-600 text-sm mt-1">
          Foundation is ready. Farm infrastructure is next.
        </p>
        <div className="mt-3 space-y-2 text-xs text-brand-700">
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span> Authentication working
          </div>
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span> Database migrations 001–005 run
          </div>
          <div className="flex items-center gap-2">
            <span className="text-green-500">✓</span> JWT tokens issued
          </div>
          <div className="flex items-center gap-2">
            <span className="text-amber-500">→</span> Sprint 1: Farm infrastructure
          </div>
        </div>
      </div>

      {/* Placeholder zones for Sprint 7 */}
      {[
        "Active Flocks",
        "ARIA Insights",
        "Financial Pulse",
        "Upcoming Tasks",
      ].map((zone) => (
        <div
          key={zone}
          className="bg-gray-50 rounded-2xl p-4 border border-dashed border-gray-200"
        >
          <p className="text-gray-400 text-sm text-center">{zone} — Sprint 7</p>
        </div>
      ))}
    </div>
  );
}
