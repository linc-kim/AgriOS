/**
 * Greena — Workspace context: the user's organizations + farms and the
 * currently-selected one (persisted in the shell store). Powers the switchers.
 */
import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";

import { organizationsAPI } from "@/api/organizations";
import { listFarms } from "@/api/farms";
import { useShellStore } from "@/stores/shellStore";

export function useWorkspace() {
  const currentOrgId = useShellStore((s) => s.currentOrgId);
  const currentFarmId = useShellStore((s) => s.currentFarmId);
  const setCurrentOrg = useShellStore((s) => s.setCurrentOrg);
  const setCurrentFarm = useShellStore((s) => s.setCurrentFarm);

  const orgsQuery = useQuery({ queryKey: ["organizations"], queryFn: organizationsAPI.list });
  const farmsQuery = useQuery({ queryKey: ["farms"], queryFn: listFarms });

  const orgs = orgsQuery.data ?? [];
  const farms = farmsQuery.data ?? [];

  const currentOrg = orgs.find((o) => o.id === currentOrgId) ?? orgs[0] ?? null;
  const currentFarm = farms.find((f) => f.id === currentFarmId) ?? farms[0] ?? null;

  // Auto-select the first org/farm when none is chosen.
  useEffect(() => {
    if (!currentOrgId && orgs[0]) setCurrentOrg(orgs[0].id);
  }, [orgs, currentOrgId, setCurrentOrg]);
  useEffect(() => {
    if (!currentFarmId && farms[0]) setCurrentFarm(farms[0].id);
  }, [farms, currentFarmId, setCurrentFarm]);

  return {
    orgs,
    farms,
    currentOrg,
    currentFarm,
    isLoading: orgsQuery.isLoading || farmsQuery.isLoading,
    isError: orgsQuery.isError || farmsQuery.isError,
    setCurrentOrg,
    setCurrentFarm,
  };
}
