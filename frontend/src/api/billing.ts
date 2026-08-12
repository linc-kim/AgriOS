/**
 * Greena — Billing API
 *
 * Paystack subscription checkout. The client only names which plan it wants;
 * the backend derives the amount from the plan (never sent from here).
 */

import apiClient from "./client";
import type { APISuccess } from "@/types";

export interface Plan {
  id: string;
  name: string;
  display_name: string;
  price_kes: number;
  is_self_serve: boolean;
}

export interface InitializePaymentResult {
  authorization_url: string;
  reference: string;
  amount_kes: number;
  plan_id: string;
  plan_name: string;
}

export interface PaymentStatus {
  reference: string | null;
  status: string; // activated | already_processed | ignored
  plan_id: string | null;
  subscription_active: boolean;
}

export interface InitializePaymentInput {
  organization_id: string;
  plan_id: string;
  callback_url?: string;
}

export const billingAPI = {
  listPlans: async (): Promise<Plan[]> => {
    const res = await apiClient.get<APISuccess<Plan[]>>("/billing/plans");
    return res.data.data;
  },

  initialize: async (payload: InitializePaymentInput): Promise<InitializePaymentResult> => {
    const res = await apiClient.post<APISuccess<InitializePaymentResult>>(
      "/billing/initialize",
      payload,
    );
    return res.data.data;
  },

  verify: async (reference: string): Promise<PaymentStatus> => {
    const res = await apiClient.get<APISuccess<PaymentStatus>>(
      `/billing/verify/${reference}`,
    );
    return res.data.data;
  },
};
