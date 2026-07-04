/**
 * A-02 — Admin Users Screen
 * /admin/users
 * List, search, suspend, restore, quota override.
 */

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { adminAPI } from "@/api/admin";
import { queryKeys } from "@/lib/queryClient";
import { Spinner } from "@/components/ui/Spinner";
import type { AdminUserSummary } from "@/types";

export default function AdminUsersScreen() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const PAGE = 50;

  const { data, isLoading } = useQuery({
    queryKey: [...queryKeys.adminUsers(), debouncedSearch, offset],
    queryFn: () => adminAPI.listUsers({ search: debouncedSearch || undefined, limit: PAGE, offset }),
  });

  const suspendMut = useMutation({
    mutationFn: ({ id }: { id: string }) =>
      adminAPI.suspendUser(id, { reason: "Admin action" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminUsers() }),
  });

  const restoreMut = useMutation({
    mutationFn: ({ id }: { id: string }) => adminAPI.restoreUser(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: queryKeys.adminUsers() }),
  });

  const handleSearch = (v: string) => {
    setSearch(v);
    clearTimeout((window as any)._adminSearchTimer);
    (window as any)._adminSearchTimer = setTimeout(() => {
      setDebouncedSearch(v);
      setOffset(0);
    }, 400);
  };

  const users: AdminUserSummary[] = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-1">{t("admin.users.title")}</h1>
      <p className="text-sm text-gray-400 mb-6">{t("admin.users.subtitle", { total })}</p>

      {/* Search */}
      <input
        type="text"
        value={search}
        onChange={(e) => handleSearch(e.target.value)}
        placeholder={t("admin.users.search_placeholder")}
        className="w-full max-w-sm mb-6 rounded-xl border border-gray-200 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-300"
      />

      {isLoading ? (
        <div className="flex justify-center py-20"><Spinner size="lg" /></div>
      ) : (
        <>
          <div className="bg-white rounded-2xl border border-gray-100 shadow-sm overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-100 text-gray-400 text-xs uppercase tracking-wide">
                  <th className="text-left px-5 py-3">{t("admin.users.col_phone")}</th>
                  <th className="text-left px-5 py-3">{t("admin.users.col_name")}</th>
                  <th className="text-center px-4 py-3">{t("admin.users.col_farms")}</th>
                  <th className="text-center px-4 py-3">{t("admin.users.col_ai")}</th>
                  <th className="text-center px-4 py-3">{t("admin.users.col_status")}</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="text-center py-12 text-gray-400">
                      {t("admin.users.empty")}
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="border-b border-gray-50 hover:bg-gray-50">
                      <td className="px-5 py-3 font-mono text-xs">{u.phone_number}</td>
                      <td className="px-5 py-3 text-gray-700">{u.name ?? "—"}</td>
                      <td className="px-4 py-3 text-center text-gray-600">{u.farm_count}</td>
                      <td className="px-4 py-3 text-center text-gray-600">{u.ai_queries_this_month}</td>
                      <td className="px-4 py-3 text-center">
                        <span
                          className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                            u.is_active
                              ? "bg-green-100 text-green-700"
                              : "bg-red-100 text-red-600"
                          }`}
                        >
                          {u.is_active ? t("admin.users.status_active") : t("admin.users.status_suspended")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        {u.is_active ? (
                          <button
                            onClick={() => suspendMut.mutate({ id: u.id })}
                            disabled={suspendMut.isPending}
                            className="text-xs text-red-500 hover:text-red-700 font-medium disabled:opacity-50"
                          >
                            {t("admin.users.action_suspend")}
                          </button>
                        ) : (
                          <button
                            onClick={() => restoreMut.mutate({ id: u.id })}
                            disabled={restoreMut.isPending}
                            className="text-xs text-brand-600 hover:text-brand-700 font-medium disabled:opacity-50"
                          >
                            {t("admin.users.action_restore")}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {total > PAGE && (
            <div className="flex justify-between items-center mt-4 text-sm text-gray-500">
              <span>{t("market.showing_of", { shown: Math.min(offset + PAGE, total), total })}</span>
              <div className="flex gap-2">
                <button
                  disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE))}
                  className="px-3 py-1 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
                >
                  {t("common.prev")}
                </button>
                <button
                  disabled={offset + PAGE >= total}
                  onClick={() => setOffset(offset + PAGE)}
                  className="px-3 py-1 rounded-lg border border-gray-200 disabled:opacity-40 hover:bg-gray-50"
                >
                  {t("common.next")}
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
