/**
 * Greena — Organizations API
 */

import apiClient from "./client";
import type { APISuccess, Organization, OrganizationCreateInput } from "@/types";

export const organizationsAPI = {
  list: async (): Promise<Organization[]> => {
    const response = await apiClient.get<APISuccess<Organization[]>>("/organizations");
    return response.data.data;
  },

  create: async (payload: OrganizationCreateInput): Promise<Organization> => {
    const response = await apiClient.post<APISuccess<Organization>>(
      "/organizations",
      payload,
    );
    return response.data.data;
  },

  get: async (id: string): Promise<Organization> => {
    const response = await apiClient.get<APISuccess<Organization>>(
      `/organizations/${id}`,
    );
    return response.data.data;
  },
};
