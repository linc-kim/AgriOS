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

export interface TrialStatus {
  is_trial: boolean;
  active: boolean;
  trial_ends_at: string | null;
  days_remaining: number;
  /** Trial-length policy from the backend (single source of truth). */
  trial_days?: number;
}

export interface ReferralStatus {
  referral_code: string | null;
  has_referral: boolean;
  referrer_org_id: string | null;
  reward_status: string | null;
  entry_open: boolean;
  entry_deadline: string | null;
}

export interface ReferralValidation {
  valid: boolean;
  reason: string | null;
}

export interface CreditEntry {
  amount_kes: number;
  source: string;
  payment_reference: string | null;
  balance_after: number;
  created_at: string;
}

export interface CreditBalance {
  balance_kes: number;
  entries: CreditEntry[];
}

export const billingAPI = {
  listPlans: async (): Promise<Plan[]> => {
    const res = await apiClient.get<APISuccess<Plan[]>>("/billing/plans");
    return res.data.data;
  },

  getTrialStatus: async (orgId: string): Promise<TrialStatus> => {
    const res = await apiClient.get<APISuccess<TrialStatus>>(`/billing/trial/${orgId}`);
    return res.data.data;
  },

  getReferralStatus: async (orgId: string): Promise<ReferralStatus> => {
    const res = await apiClient.get<APISuccess<ReferralStatus>>(`/billing/referral/${orgId}`);
    return res.data.data;
  },

  validateReferral: async (orgId: string, code: string): Promise<ReferralValidation> => {
    const res = await apiClient.get<APISuccess<ReferralValidation>>(
      `/billing/referral/${orgId}/validate`,
      { params: { code } },
    );
    return res.data.data;
  },

  submitReferral: async (orgId: string, code: string): Promise<ReferralStatus> => {
    const res = await apiClient.post<APISuccess<ReferralStatus>>(
      `/billing/referral/${orgId}`,
      { code },
    );
    return res.data.data;
  },

  getCredits: async (orgId: string): Promise<CreditBalance> => {
    const res = await apiClient.get<APISuccess<CreditBalance>>(`/billing/credits/${orgId}`);
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
