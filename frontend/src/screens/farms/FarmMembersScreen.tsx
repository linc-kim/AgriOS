/**
 * AGRIOS — Screen FM-03: Farm Members
 * Lists all members with their status badge and role.
 * Farm owner / manager can suspend, update role, or remove members.
 */

import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listFarmMembers, removeFarmMember } from "@/api/farms";
import { queryKeys } from "@/lib/queryClient";
import { UserPlus, Trash2 } from "lucide-react";
import type { FarmMember } from "@/types";

function StatusBadge({ status }: { status: FarmMember["status"] }) {
  const { t } = useTranslation();
  const classes = {
    active: "bg-green-100 text-green-700",
    pending: "bg-amber-100 text-amber-700",
    suspended: "bg-red-100 text-red-700",
  }[status];
  const labels = {
    active: t("farm.members.status_active"),
    pending: t("farm.members.status_pending"),
    suspended: t("farm.members.status_suspended"),
  };
  return (
    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${classes}`}>
      {labels[status]}
    </span>
  );
}

export default function FarmMembersScreen() {
  const { farmId } = useParams<{ farmId: string }>();
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: members = [], isLoading } = useQuery({
    queryKey: queryKeys.farmMembers(farmId!),
    queryFn: () => listFarmMembers(farmId!),
    enabled: !!farmId,
  });

  const removeMutation = useMutation({
    mutationFn: ({ memberId }: { memberId: string }) =>
      removeFarmMember(farmId!, memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.farmMembers(farmId!) });
      queryClient.invalidateQueries({ queryKey: queryKeys.farm(farmId!) });
    },
  });

  function handleRemove(member: FarmMember) {
    const displayName = member.full_name || member.phone || "this member";
    if (window.confirm(`Remove ${displayName} from the farm?`)) {
      removeMutation.mutate({ memberId: member.id });
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <div className="bg-white border-b border-gray-100 px-4 pt-12 pb-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="min-h-[48px] min-w-[48px] flex items-center justify-center text-gray-600"
          >
            ←
          </button>
          <h1 className="text-lg font-bold text-gray-900">
            {t("farm.members.title")}
          </h1>
        </div>
        <button
          onClick={() => navigate(`/farms/${farmId}/members/invite`)}
          className="
            min-h-[40px] px-4 rounded-xl bg-brand-600 text-white
            text-sm font-semibold flex items-center gap-1.5
          "
        >
          <UserPlus className="w-4 h-4" />
          {t("farm.members.invite")}
        </button>
      </div>

      {/* List */}
      <div className="flex-1 px-4 py-4 flex flex-col gap-2">
        {isLoading && (
          <div className="flex justify-center pt-12">
            <div className="w-8 h-8 border-2 border-brand-600 border-t-transparent rounded-full animate-spin" />
          </div>
        )}

        {!isLoading && members.length === 0 && (
          <div className="text-center text-gray-500 pt-16 text-sm">
            No members yet.
          </div>
        )}

        {members.map((member) => (
          <div
            key={member.id}
            className="bg-white rounded-xl px-4 py-4 flex items-center gap-3 shadow-sm"
          >
            {/* Avatar initials */}
            <div className="w-10 h-10 rounded-full bg-brand-100 flex items-center justify-center shrink-0">
              <span className="text-brand-700 font-bold text-sm">
                {(member.full_name || member.phone || "?")
                  .split(" ")
                  .slice(0, 2)
                  .map((n) => n[0])
                  .join("")
                  .toUpperCase()}
              </span>
            </div>

            {/* Info */}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-semibold text-gray-900 text-sm truncate">
                  {member.full_name || member.user_phone || member.phone || "Invited user"}
                </span>
                <StatusBadge status={member.status} />
              </div>
              <div className="text-xs text-gray-500 mt-0.5">
                {t(`farm.roles.${member.role_name}` as any) || member.role_display_name}
                {member.phone && member.full_name && (
                  <span className="ml-2 text-gray-400">· {member.phone}</span>
                )}
              </div>
            </div>

            {/* Remove button (not for farm_owner) */}
            {member.role_name !== "farm_owner" && (
              <button
                onClick={() => handleRemove(member)}
                disabled={removeMutation.isPending}
                className="
                  min-h-[40px] min-w-[40px] flex items-center justify-center
                  rounded-lg text-gray-400 hover:text-red-500 hover:bg-red-50
                  transition-colors
                "
                aria-label={t("farm.members.remove")}
              >
                <Trash2 className="w-4 h-4" />
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
