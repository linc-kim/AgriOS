/**
 * Greena — Screen FM-01: Farm Management Hub
 * Central screen for a single farm. Shows summary, tabs for Members / Structure.
 * Accessible from Dashboard → farm card.
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { getFarm } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import { ChevronRight, Users, Building2, Pencil } from "lucide-react";

export default function FarmManagementScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data: farm, isLoading, error } = useQuery({
    queryKey: queryKeys.farm(farmId!),
    queryFn: () => getFarm(farmId!),
    enabled: !!farmId,
  });

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !farm) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center px-6 gap-4">
        <p className="text-gray-600 text-center">{t("common.error")}</p>
        <button
          onClick={() => navigate(-1)}
          className="text-brand-600 font-semibold text-sm"
        >
          {t("common.retry")}
        </button>
      </div>
    );
  }

  const menuItems = [
    {
      label: t("farm.management.members_tab"),
      icon: <Users className="w-5 h-5 text-brand-600" />,
      count: farm.member_count,
      route: `/farms/${farmId}/members`,
    },
    {
      label: t("farm.management.structure_tab"),
      icon: <Building2 className="w-5 h-5 text-brand-600" />,
      count: farm.house_count,
      route: `/farms/${farmId}/structure`,
    },
  ];

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-brand-600 px-6 pt-12 pb-8">
        <button
          onClick={() => navigate(-1)}
          className="text-white/70 text-sm mb-4 flex items-center gap-1"
        >
          ← Back
        </button>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-white text-xl font-bold">{farm.name}</h1>
            {farm.county && (
              <p className="text-white/70 text-sm mt-0.5">{farm.county}</p>
            )}
          </div>
          <button
            onClick={() => navigate(`/farms/${farmId}/edit`)}
            className="p-2 rounded-lg bg-white/10 active:bg-white/20"
            aria-label={t("farm.management.edit")}
          >
            <Pencil className="w-4 h-4 text-white" />
          </button>
        </div>

        {/* Stats row */}
        <div className="mt-5 flex gap-4">
          {[
            { label: "Members", value: farm.member_count },
            { label: "Houses", value: farm.house_count },
            { label: "Plan", value: farm.plan?.display_name ?? "Free" },
          ].map((stat) => (
            <div key={stat.label} className="bg-white/10 rounded-xl px-3 py-2 min-w-[72px]">
              <div className="text-white text-lg font-bold leading-none">{stat.value}</div>
              <div className="text-white/60 text-xs mt-0.5">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Menu */}
      <div className="flex-1 px-4 py-4 flex flex-col gap-2">
        {menuItems.map((item) => (
          <button
            key={item.route}
            onClick={() => navigate(item.route)}
            className="
              flex items-center justify-between w-full
              bg-white rounded-xl px-4 min-h-[64px]
              shadow-sm active:bg-gray-50
            "
          >
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-brand-50 flex items-center justify-center">
                {item.icon}
              </div>
              <span className="font-semibold text-gray-800">{item.label}</span>
            </div>
            <div className="flex items-center gap-2">
              {item.count > 0 && (
                <span className="text-sm text-gray-400">{item.count}</span>
              )}
              <ChevronRight className="w-4 h-4 text-gray-400" />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
