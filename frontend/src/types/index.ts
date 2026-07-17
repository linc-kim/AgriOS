/**
 * Greena — Core TypeScript Types
 * All API response shapes are defined here.
 * Keep in sync with backend Pydantic schemas.
 */

// ── API Envelope ──────────────────────────────────────────────────────────────

export interface APISuccess<T> {
  success: true;
  data: T;
  meta?: Record<string, unknown>;
}

export interface APIError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>[];
  };
}

export interface PaginationMeta {
  total: number;
  page: number;
  limit: number;
  pages: number;
}

export interface APIList<T> {
  success: true;
  data: T[];
  meta: PaginationMeta;
}

// ── Auth Types ────────────────────────────────────────────────────────────────

export interface Role {
  id: string;
  name: RoleName;
  display_name: string;
}

export type RoleName =
  | "super_admin"
  | "platform_admin"
  | "enterprise_owner"
  | "farm_owner"
  | "farm_manager"
  | "vet_consultant"
  | "farm_worker"
  | "viewer";

export interface UserRole {
  role: Role;
  farm_id: string | null;
}

export interface User {
  id: string;
  phone: string | null;
  email: string | null;
  full_name: string | null;
  language: "en" | "sw";
  is_phone_verified: boolean;
  email_verified: boolean;
  has_pin: boolean;
  has_password: boolean;
  sms_notifications_enabled: boolean;
  user_roles: UserRole[];
  created_at: string;
  updated_at: string;
}

// ── Organizations (Phase 2) ─────────────────────────────────────────────────

export interface Organization {
  id: string;
  name: string;
  slug: string;
  country: string | null;
  timezone: string;
  currency: string;
  role: RoleName | null;
  created_at: string;
  updated_at: string;
}

export interface OrganizationCreateInput {
  name: string;
  country?: string | null;
  timezone?: string | null;
  currency?: string | null;
}

// Sprint 9 — Settings API types
export interface UserUpdateInput {
  full_name?: string | null;
  language?: "en" | "sw";
  sms_notifications_enabled?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "Bearer";
  expires_in: number;
  is_new_user: boolean;
  has_pin: boolean;
}

// ── App State ─────────────────────────────────────────────────────────────────

export type Language = "en" | "sw";

export type AuthState = "unauthenticated" | "authenticated" | "loading";

// ── Subscription Plans ────────────────────────────────────────────────────────

export type PlanKey = "free" | "starter" | "pro";

export interface SubscriptionPlan {
  key: PlanKey;
  display_name: string;
  price_kes: number;
  ai_queries_per_month: number | null; // null = unlimited
  max_houses: number | null;
  max_active_flocks: number | null;
  max_members: number;
}

// ── Farm Infrastructure Types ─────────────────────────────────────────────────

export type MemberStatus = "pending" | "active" | "suspended";
export type HouseType = "broiler" | "layer" | "breeder" | "pullet" | "multi";

export interface Farm {
  id: string;
  name: string;
  description: string | null;
  location: string | null;
  county: string | null;
  owner_id: string;
  plan_id: string;
  is_active: boolean;
  timezone: string;
  member_count: number;
  unit_count: number;
  house_count: number;
  plan: SubscriptionPlan | null;
  created_at: string;
  updated_at: string;
}

export interface FarmSummary {
  id: string;
  name: string;
  location: string | null;
  county: string | null;
  is_active: boolean;
  member_count: number;
  plan_name: string;
  created_at: string;
}

export interface FarmMember {
  id: string;
  farm_id: string;
  user_id: string | null;
  phone: string | null;
  status: MemberStatus;
  accepted_at: string | null;
  role_name: RoleName;
  role_display_name: string;
  full_name: string | null;
  user_phone: string | null;
  created_at: string;
  updated_at: string;
}

export interface FarmUnit {
  id: string;
  farm_id: string;
  name: string;
  description: string | null;
  sort_order: number;
  house_count: number;
  created_at: string;
  updated_at: string;
}

export interface ProductionHouse {
  id: string;
  farm_id: string;
  unit_id: string;
  name: string;
  capacity: number;
  house_type: HouseType;
  sort_order: number;
  current_flock_id: string | null;
  is_occupied: boolean;
  created_at: string;
  updated_at: string;
}

// ── Farm API Request Bodies ───────────────────────────────────────────────────

export interface FarmCreateInput {
  name: string;
  description?: string;
  location?: string;
  county?: string;
  organization_id?: string;
}

export interface FarmUpdateInput {
  name?: string;
  description?: string;
  location?: string;
  county?: string;
}

export interface FarmMemberInviteInput {
  phone: string;
  role_name: Exclude<RoleName, "farm_owner" | "super_admin" | "platform_admin" | "enterprise_owner">;
}

export interface FarmMemberUpdateInput {
  status?: "active" | "suspended";
  role_name?: string;
}

export interface FarmUnitCreateInput {
  name: string;
  description?: string;
  sort_order?: number;
}

export interface FarmUnitUpdateInput {
  name?: string;
  description?: string;
  sort_order?: number;
}

export interface ProductionHouseCreateInput {
  name: string;
  capacity: number;
  house_type?: HouseType;
  sort_order?: number;
}

export interface ProductionHouseUpdateInput {
  name?: string;
  capacity?: number;
  house_type?: HouseType;
  sort_order?: number;
}

// ── Flock Types ───────────────────────────────────────────────────────────────

export type FlockStatus = "active" | "sold" | "closed" | "culled";
export type CloseStatus = "sold" | "closed" | "culled";

export interface Flock {
  id: string;
  farm_id: string;
  house_id: string;
  species_key: string;
  name: string;
  breed: string | null;
  source: string | null;
  batch_number: string | null;
  initial_count: number;
  placement_date: string;
  expected_cycle_days: number;
  expected_close_date: string | null;
  status: FlockStatus;
  archived_at: string | null;
  close_date: string | null;
  close_reason: string | null;
  sale_price_per_kg: string | null;
  total_birds_sold: number | null;
  closing_weight_kg: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface FlockMetrics {
  days_alive: number;
  total_mortality: number;
  total_culls: number;
  current_count: number;
  survival_rate: number;
  total_feed_kg: string;
  latest_avg_weight_kg: string | null;
  total_biomass_kg: string | null;
  fcr: string | null;
  total_eggs_collected: number | null;
  hen_day_production: number | null;
}

export interface FlockDetail extends Flock {
  metrics: FlockMetrics;
}

export interface DailyLog {
  id: string;
  farm_id: string;
  flock_id: string;
  log_date: string;
  morning_count: number | null;
  mortality_count: number;
  mortality_cause: string | null;
  culls: number;
  feed_consumed_kg: string;
  water_litres: string | null;
  house_temp_am: string | null;
  house_temp_pm: string | null;
  notes: string | null;
  logged_by: string | null;
  is_corrected: boolean;
  corrected_by: string | null;
  corrected_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProductionRecord {
  id: string;
  farm_id: string;
  flock_id: string;
  record_date: string;
  eggs_collected: number;
  broken_eggs: number;
  saleable_eggs: number;
  hen_day_production: string | null;
  notes: string | null;
  logged_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface WeighinRecord {
  id: string;
  farm_id: string;
  flock_id: string;
  weighed_at: string;
  sample_size: number;
  average_weight_kg: string;
  min_weight_kg: string | null;
  max_weight_kg: string | null;
  total_biomass_kg: string | null;
  fcr_to_date: string | null;
  notes: string | null;
  logged_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedPurchase {
  id: string;
  farm_id: string;
  flock_id: string | null;
  purchase_date: string;
  feed_type: string;
  quantity_kg: string;
  price_per_kg: string;
  total_cost: string;
  supplier: string | null;
  notes: string | null;
  recorded_by: string | null;
  created_at: string;
  updated_at: string;
}

// ── Flock API Request Bodies ──────────────────────────────────────────────────

export interface FlockCreateInput {
  house_id: string;
  name: string;
  breed?: string;
  source?: string;
  batch_number?: string;
  initial_count: number;
  placement_date: string;
  expected_cycle_days?: number;
  species_key?: string;
}

export interface FlockUpdateInput {
  name?: string;
  breed?: string;
  source?: string;
  batch_number?: string;
  house_id?: string;
  expected_cycle_days?: number;
}

export interface FarmProductionDashboard {
  active_flock_count: number;
  total_birds: number;
  avg_bird_age_days: number | null;
  eggs_today: number;
  eggs_this_week: number;
  avg_hen_day_production: number | null;
  feed_today_kg: string;
  feed_this_week_kg: string;
  mortality_this_week: number;
  culls_this_week: number;
}

export interface FlockCloseInput {
  status: CloseStatus;
  close_date: string;
  close_reason?: string;
  sale_price_per_kg?: string;
  total_birds_sold?: number;
  closing_weight_kg?: string;
}

export interface DailyLogSubmitInput {
  log_date: string;
  morning_count?: number;
  mortality_count?: number;
  mortality_cause?: string;
  culls?: number;
  feed_consumed_kg?: string;
  water_litres?: string;
  house_temp_am?: string;
  house_temp_pm?: string;
  notes?: string;
}

export interface ProductionRecordInput {
  record_date: string;
  eggs_collected?: number;
  broken_eggs?: number;
  notes?: string;
}

export interface WeighinInput {
  weighed_at: string;
  sample_size: number;
  average_weight_kg: string;
  min_weight_kg?: string;
  max_weight_kg?: string;
  notes?: string;
}

export interface FeedPurchaseInput {
  flock_id?: string;
  purchase_date: string;
  feed_type: string;
  quantity_kg: string;
  price_per_kg: string;
  supplier?: string;
  notes?: string;
}

// ── Health Types ─────────────────────────────────────────────────────────────

export type AlertStatus = "draft" | "active" | "deactivated";
export type AlertSeverity = "info" | "warning" | "critical";

export interface VaccinationRecord {
  id: string;
  farm_id: string;
  flock_id: string;
  species_key: string;
  vaccine_name: string;
  vaccine_brand: string | null;
  dose_number: number;
  administered_date: string;
  administered_by: string | null;
  route: string | null;
  flock_age_days: number | null;
  batch_number: string | null;
  next_due_date: string | null;
  next_vaccine_name: string | null;
  notes: string | null;
  is_overdue: boolean;
  is_due_soon: boolean;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface VaccinationScheduleItem {
  id: string;
  flock_id: string;
  flock_name: string;
  vaccine_name: string;
  next_vaccine_name: string | null;
  next_due_date: string;
  dose_number: number;
  is_overdue: boolean;
  days_until_due: number;
}

export interface UpcomingVaccinationsResponse {
  overdue: VaccinationScheduleItem[];
  due_today: VaccinationScheduleItem[];
  due_this_week: VaccinationScheduleItem[];
  upcoming: VaccinationScheduleItem[];
}

export interface DiseaseAlert {
  id: string;
  disease_name: string;
  title: string;
  description: string;
  brief_guidance: string | null;
  severity: AlertSeverity;
  status: AlertStatus;
  county: string | null;
  species_key: string | null;
  published_at: string | null;
  expires_at: string | null;
  deactivated_at: string | null;
  published_by: string | null;
  sms_dispatched_at: string | null;
  sms_recipient_count: number | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  is_expired: boolean;
}

export interface ActiveAlertSummary {
  id: string;
  disease_name: string;
  title: string;
  brief_guidance: string | null;
  severity: AlertSeverity;
  county: string | null;
  published_at: string | null;
}

// ── Health API Request Bodies ─────────────────────────────────────────────────

export interface VaccinationRecordCreateInput {
  vaccine_name: string;
  vaccine_brand?: string;
  dose_number?: number;
  administered_date: string;
  route?: string;
  flock_age_days?: number;
  batch_number?: string;
  next_due_date?: string;
  next_vaccine_name?: string;
  notes?: string;
}

export interface VaccinationRecordUpdateInput {
  vaccine_name?: string;
  vaccine_brand?: string;
  dose_number?: number;
  administered_date?: string;
  route?: string;
  batch_number?: string;
  next_due_date?: string;
  next_vaccine_name?: string;
  notes?: string;
  correction_reason: string;
}

// ── Finance Types ─────────────────────────────────────────────────────────────

export type RevenueType = "eggs" | "birds" | "manure" | "other";
export type PaymentMethod = "cash" | "mpesa" | "bank_transfer" | "credit";

export interface ExpenseCategory {
  id: string;
  farm_id: string | null;
  name: string;
  slug: string;
  icon: string | null;
  color: string | null;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface ExpenseSummaryItem {
  id: string;
  expense_date: string;
  amount: string;
  description: string;
  category_name: string;
  category_icon: string | null;
  category_color: string | null;
  payment_method: string | null;
  flock_id: string | null;
}

export interface Expense {
  id: string;
  farm_id: string;
  flock_id: string | null;
  category_id: string;
  category: ExpenseCategory;
  expense_date: string;
  amount: string;
  description: string;
  payment_method: string | null;
  receipt_url: string | null;
  supplier: string | null;
  quantity: string | null;
  unit: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExpenseListResponse {
  items: ExpenseSummaryItem[];
  total: number;
  page: number;
  page_size: number;
  total_kes: string;
}

export interface RevenueSummaryItem {
  id: string;
  revenue_date: string;
  revenue_type: RevenueType;
  amount: string;
  quantity: string | null;
  unit: string | null;
  buyer_name: string | null;
  payment_method: string | null;
  flock_id: string;
}

export interface RevenueRecord {
  id: string;
  farm_id: string;
  flock_id: string;
  revenue_type: RevenueType;
  revenue_date: string;
  amount: string;
  quantity: string | null;
  unit: string | null;
  unit_price: string | null;
  birds_sold: number | null;
  avg_weight_kg: string | null;
  eggs_count: number | null;
  trays_count: number | null;
  buyer_name: string | null;
  buyer_phone: string | null;
  payment_method: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface RevenueListResponse {
  items: RevenueSummaryItem[];
  total: number;
  page: number;
  page_size: number;
  total_kes: string;
}

export interface FinancialSnapshot {
  id: string;
  farm_id: string;
  flock_id: string;
  snapshot_at: string;
  // Revenue
  total_revenue_kes: string;
  revenue_eggs_kes: string;
  revenue_birds_kes: string;
  revenue_manure_kes: string;
  revenue_other_kes: string;
  // Expenses
  total_expenses_kes: string;
  feed_cost_kes: string;
  doc_cost_kes: string;
  vet_health_cost_kes: string;
  labour_cost_kes: string;
  other_cost_kes: string;
  // P&L
  gross_profit_kes: string;
  gross_margin_pct: string | null;
  is_profitable: boolean;
  // Per-bird
  cost_per_bird_kes: string | null;
  revenue_per_bird_kes: string | null;
  break_even_price_kes: string | null;
  // FCR
  total_feed_kg: string;
  fcr_computed: string | null;
  // State
  bird_count_snapshot: number | null;
  birds_sold_snapshot: number | null;
  feed_cost_pct: string | null;
  updated_at: string;
}

export interface FlockPnLCard {
  flock_id: string;
  flock_name: string;
  flock_status: string;
  snapshot_at: string | null;
  total_revenue_kes: string;
  total_expenses_kes: string;
  gross_profit_kes: string;
  gross_margin_pct: string | null;
  is_profitable: boolean;
  days_alive: number | null;
}

export interface FinanceDashboardResponse {
  period_label: string;
  total_revenue_kes: string;
  total_expenses_kes: string;
  gross_profit_kes: string;
  gross_margin_pct: string | null;
  is_profitable: boolean;
  feed_cost_kes: string;
  feed_cost_pct: string | null;
  doc_cost_kes: string;
  vet_health_cost_kes: string;
  labour_cost_kes: string;
  other_cost_kes: string;
  flock_cards: FlockPnLCard[];
  recent_expenses: ExpenseSummaryItem[];
  recent_revenue: RevenueSummaryItem[];
}

export interface ExpenseCategoryBreakdown {
  category_id: string;
  category_name: string;
  category_icon: string | null;
  category_color: string | null;
  total_kes: string;
  pct_of_total: string | null;
  transaction_count: number;
}

// Finance API Request Bodies
export interface ExpenseCategoryCreateInput {
  name: string;
  slug: string;
  icon?: string;
  color?: string;
}

export interface ExpenseCreateInput {
  flock_id?: string;
  category_id: string;
  expense_date: string;
  amount: string;
  description: string;
  payment_method?: PaymentMethod;
  supplier?: string;
  quantity?: string;
  unit?: string;
  notes?: string;
}

export interface ExpenseUpdateInput {
  category_id?: string;
  flock_id?: string;
  expense_date?: string;
  amount?: string;
  description?: string;
  payment_method?: PaymentMethod;
  supplier?: string;
  notes?: string;
  correction_reason: string;
}

export interface RevenueRecordCreateInput {
  flock_id: string;
  revenue_type: RevenueType;
  revenue_date: string;
  amount: string;
  quantity?: string;
  unit?: string;
  unit_price?: string;
  birds_sold?: number;
  avg_weight_kg?: string;
  eggs_count?: number;
  trays_count?: number;
  buyer_name?: string;
  buyer_phone?: string;
  payment_method?: PaymentMethod;
  notes?: string;
}

export interface RevenueRecordUpdateInput {
  revenue_type?: RevenueType;
  revenue_date?: string;
  amount?: string;
  birds_sold?: number;
  avg_weight_kg?: string;
  eggs_count?: number;
  trays_count?: number;
  buyer_name?: string;
  payment_method?: PaymentMethod;
  notes?: string;
  correction_reason: string;
}

// Calculator types
export interface FCRCalculatorResult {
  fcr: string;
  interpretation: string;
  feed_kg: string;
  live_weight_kg: string;
}

export interface ProfitProjectionResult {
  birds_at_sale: number;
  total_live_weight_kg: string;
  projected_revenue_kes: string;
  projected_total_expenses_kes: string;
  projected_profit_kes: string;
  projected_margin_pct: string;
  revenue_per_bird_kes: string;
  cost_per_bird_kes: string;
  is_profitable: boolean;
}

export interface BreakEvenResult {
  break_even_per_kg_kes: string;
  break_even_per_bird_kes: string;
  total_live_weight_kg: string;
  total_expenses_kes: string;
}

export interface FeedNeedsResult {
  total_feed_needed_kg: string;
  feed_per_day_kg: string | null;
  estimated_feed_cost_kes: string | null;
  weight_gain_needed_kg: string;
  current_biomass_kg: string;
  target_biomass_kg: string;
}

// ── Notification ──────────────────────────────────────────────────────────────

export type NotificationType =
  | "otp"
  | "farm_invite"
  | "vaccination_reminder"
  | "vaccination_overdue"
  | "daily_log_reminder"
  | "disease_alert"
  | "weekly_summary";

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  is_read: boolean;
  reference_id: string | null;
  created_at: string;
}

// ── AI / ARIA (Sprint 6) ──────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant";
export type AIProvider = "gemini" | "claude";
export type InsightSeverity = "info" | "warning" | "alert" | "reminder";
export type RecommendationStatus = "pending" | "acted" | "dismissed" | "expired";

export interface AIMessage {
  id: string;
  conversation_id: string;
  role: MessageRole;
  content: string;
  language: string;
  provider: AIProvider | null;
  total_tokens: number | null;
  latency_ms: number | null;
  created_at: string;
}

export interface AIConversationSummary {
  id: string;
  farm_id: string;
  flock_id: string | null;
  title: string | null;
  message_count: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AIConversationDetail extends AIConversationSummary {
  messages: AIMessage[];
}

export interface ARIAResponse {
  conversation_id: string;
  message: AIMessage;
  quota_remaining: number | null;
  used_fallback: boolean;
}

export interface AIInsight {
  id: string;
  farm_id: string;
  flock_id: string | null;
  insight_type: string;
  severity: InsightSeverity;
  title: string;
  body: string;
  action_route: string | null;
  action_label: string | null;
  is_dismissed: boolean;
  dismissed_at: string | null;
  generated_at: string;
  expires_at: string | null;
  created_at: string;
}

export interface AIInsightListResponse {
  items: AIInsight[];
  total: number;
  alert_count: number;
  warning_count: number;
  info_count: number;
  reminder_count: number;
}

export interface AIRecommendation {
  id: string;
  farm_id: string;
  flock_id: string | null;
  recommendation_type: string;
  title: string;
  body: string;
  action_label: string | null;
  action_route: string | null;
  status: RecommendationStatus;
  acted_at: string | null;
  dismissed_at: string | null;
  expires_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AIRecommendationListResponse {
  items: AIRecommendation[];
  total: number;
  pending_count: number;
}

export interface AIUsageResponse {
  plan_name: string;
  monthly_limit: number | null;
  queries_used_this_month: number;
  queries_remaining: number | null;
  cost_usd_this_month: number;
  total_queries_all_time: number;
}

// Input types
export interface ARIAMessageCreate {
  content: string;
  conversation_id?: string;
  flock_id?: string;
}

// ── Platform Layer — Sprint 7 (Migrations 028-030) ───────────────────────────

// Notifications (Migration 028)
export interface Notification {
  id: string;
  farm_id: string;
  user_id: string;
  notification_type: string;
  title: string;
  body: string;
  action_route: string | null;
  is_read: boolean;
  read_at: string | null;
  source: string | null;
  created_at: string;
  updated_at: string;
}

export interface NotificationListResponse {
  items: Notification[];
  total: number;
  unread_count: number;
}

// Market Prices (Migration 030)
export interface MarketPrice {
  id: string;
  commodity: string;
  price_kes: string;        // Decimal serialised as string
  unit: string;
  county: string | null;
  source: string | null;
  valid_date: string;       // ISO date YYYY-MM-DD
  recorded_by_id: string | null;
  created_at: string;
}

export interface MarketPriceListResponse {
  items: MarketPrice[];
  total: number;
  as_of_date: string | null;
}

export interface CommodityListResponse {
  commodities: string[];
}

// Input types
export interface MarketPriceCreate {
  commodity: string;
  price_kes: string;
  unit: string;
  county?: string;
  source?: string;
  valid_date: string;
}

// ── Admin Module — Sprint 8 ────────────────────────────────────────────────────

export interface PlatformStats {
  total_users: number;
  active_users_30d: number;
  total_farms: number;
  active_farms_30d: number;
  total_flocks: number;
  active_flocks: number;
  total_ai_queries_30d: number;
  total_ai_cost_usd_30d: number;
  total_notifications_sent_30d: number;
  total_disease_alerts_active: number;
  total_market_prices: number;
}

export interface AdminUserSummary {
  id: string;
  phone_number: string;
  name: string | null;
  is_active: boolean;
  is_verified: boolean;
  farm_count: number;
  ai_queries_this_month: number;
  created_at: string;
}

export interface AdminUserDetail extends AdminUserSummary {
  farms: { id: string; name: string }[];
  roles: string[];
  ai_queries_all_time: number;
}

export interface AdminUserListResponse {
  items: AdminUserSummary[];
  total: number;
}

export interface AdminFarmSummary {
  id: string;
  name: string;
  owner_phone: string | null;
  owner_name: string | null;
  subscription_plan: string;
  member_count: number;
  active_flock_count: number;
  last_log_date: string | null;
  created_at: string;
}

export interface AdminFarmListResponse {
  items: AdminFarmSummary[];
  total: number;
}

export interface AdminAIUsageDay {
  date: string;
  query_count: number;
  total_tokens: number;
  cost_usd: number;
  unique_users: number;
}

export interface AdminAIUsageResponse {
  period_days: number;
  total_queries: number;
  total_tokens: number;
  total_cost_usd: number;
  unique_users: number;
  daily_breakdown: AdminAIUsageDay[];
  top_model: string | null;
  fallback_rate_pct: number;
}

export interface SubscriptionPlanSummary {
  id: string;
  name: string;
  display_name: string;
  price_kes: string;
  farm_count: number;
}

// Admin input types
export interface AdminUserSuspendInput { reason: string; }
export interface AdminUserQuotaInput { monthly_limit: number | null; reason: string; }
export interface AdminFarmPlanInput { plan_name: string; reason: string; }

// ── Health Events (Phase 3 Health module) ─────────────────────────────────────

export type HealthEventType =
  | "observation" | "symptom" | "diagnosis" | "treatment" | "medication"
  | "mortality_investigation" | "quarantine" | "vet_visit" | "recovery" | "followup";
export type HealthSeverity = "info" | "watch" | "warning" | "critical";
export type HealthStatus = "open" | "monitoring" | "resolved";

export interface HealthEvent {
  id: string;
  farm_id: string;
  flock_id: string;
  event_type: HealthEventType;
  event_date: string;
  title: string;
  symptoms: string[];
  observations: Record<string, unknown>;
  attachments: string[];
  diagnosis: string | null;
  treatment: string | null;
  medication_name: string | null;
  dosage: string | null;
  severity: HealthSeverity;
  affected_count: number | null;
  status: HealthStatus;
  resolved_date: string | null;
  vet_name: string | null;
  follow_up_date: string | null;
  cost_kes: string | null;
  expense_id: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealthEventCreateInput {
  event_type: HealthEventType;
  event_date: string;
  title: string;
  symptoms?: string[];
  observations?: Record<string, unknown>;
  diagnosis?: string;
  treatment?: string;
  medication_name?: string;
  dosage?: string;
  severity?: HealthSeverity;
  affected_count?: number;
  status?: HealthStatus;
  vet_name?: string;
  follow_up_date?: string;
  cost_kes?: string;
  notes?: string;
}

export interface HealthEventUpdateInput {
  title?: string;
  symptoms?: string[];
  diagnosis?: string;
  treatment?: string;
  severity?: HealthSeverity;
  affected_count?: number;
  status?: HealthStatus;
  resolved_date?: string;
  vet_name?: string;
  follow_up_date?: string;
  notes?: string;
}

export interface HealthFollowUp {
  id: string;
  flock_id: string;
  title: string;
  follow_up_date: string;
  severity: HealthSeverity;
  status: HealthStatus;
}

export interface FlockHealthSummary {
  open_events: number;
  monitoring_events: number;
  resolved_events: number;
  critical_open: number;
  total_affected_open: number;
  upcoming_follow_ups: HealthFollowUp[];
  active_alert_count: number;
  overdue_vaccinations: number;
}

// ── Feed Management (Phase 3, Module 4) ───────────────────────────────────────

export interface FeedSupplier {
  id: string;
  farm_id: string;
  name: string;
  contact_name?: string | null;
  phone?: string | null;
  email?: string | null;
  location?: string | null;
  feed_types: string[];
  rating?: string | null;
  is_active: boolean;
  notes?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  total_spend_kes?: string | null;
  purchase_count?: number | null;
  total_kg_purchased?: string | null;
}

export interface FeedSupplierInput {
  name: string;
  contact_name?: string;
  phone?: string;
  email?: string;
  location?: string;
  feed_types?: string[];
  rating?: string;
  notes?: string;
}

export interface FeedInventoryItem {
  id: string;
  farm_id: string;
  feed_type: string;
  name?: string | null;
  brand?: string | null;
  batch_number?: string | null;
  expiry_date?: string | null;
  location: string;
  unit: string;
  quantity_kg: string;
  avg_cost_per_kg: string;
  reorder_level_kg?: string | null;
  supplier_id?: string | null;
  supplier_name?: string | null;
  is_active: boolean;
  notes?: string | null;
  stock_value_kes: string;
  is_low_stock: boolean;
  days_to_expiry?: number | null;
  is_expired: boolean;
  is_expiring_soon: boolean;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}

export interface FeedInventoryItemInput {
  feed_type: string;
  name?: string;
  brand?: string;
  batch_number?: string;
  expiry_date?: string;
  location?: string;
  unit?: string;
  reorder_level_kg?: string;
  supplier_id?: string;
  opening_quantity_kg?: string;
  opening_cost_per_kg?: string;
  notes?: string;
}

export type FeedTxnType =
  | "purchase"
  | "consumption"
  | "transfer_out"
  | "transfer_in"
  | "wastage"
  | "adjustment";

export interface FeedTransaction {
  id: string;
  farm_id: string;
  item_id: string;
  flock_id?: string | null;
  txn_type: FeedTxnType;
  direction: number;
  txn_date: string;
  quantity_kg: string;
  unit_cost_per_kg: string;
  total_cost: string;
  supplier_id?: string | null;
  counterparty_item_id?: string | null;
  reason?: string | null;
  reference?: string | null;
  expense_id?: string | null;
  notes?: string | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  feed_type?: string | null;
  location?: string | null;
  flock_name?: string | null;
}

export interface FeedPurchaseModuleInput {
  item_id?: string;
  feed_type?: string;
  location?: string;
  quantity_kg: string;
  price_per_kg: string;
  purchase_date: string;
  supplier_id?: string;
  supplier_name?: string;
  reference?: string;
  delivery_date?: string;
  brand?: string;
  batch_number?: string;
  expiry_date?: string;
  flock_id?: string;
  notes?: string;
}

export interface FeedConsumptionInput {
  item_id: string;
  flock_id: string;
  quantity_kg: string;
  consumption_date: string;
  notes?: string;
}

export interface FeedTransferInput {
  from_item_id: string;
  to_location: string;
  quantity_kg: string;
  transfer_date: string;
  reason?: string;
  notes?: string;
}

export interface FeedWastageInput {
  item_id: string;
  quantity_kg: string;
  wastage_date: string;
  reason?: string;
  flock_id?: string;
  notes?: string;
}

export interface FeedReorderAlert {
  item_id: string;
  feed_type: string;
  location: string;
  quantity_kg: string;
  reorder_level_kg: string;
  shortfall_kg: string;
  supplier_id?: string | null;
  supplier_name?: string | null;
}

export interface FeedDashboard {
  total_stock_kg: string;
  total_stock_value_kes: string;
  item_count: number;
  low_stock_count: number;
  expiring_count: number;
  window_days: number;
  purchased_kg: string;
  purchased_cost_kes: string;
  consumed_kg: string;
  consumed_cost_kes: string;
  consumed_today_kg: string;
  consumed_week_kg: string;
  wasted_kg: string;
  wasted_cost_kes: string;
  reorder_alerts: FeedReorderAlert[];
  expiry_alerts: FeedExpiryAlert[];
  top_flocks: FeedTopFlock[];
  forecast: FeedForecast;
  items: FeedInventoryItem[];
  recent_transactions: FeedTransaction[];
}

export interface FeedUsagePoint {
  period: string;
  consumed_kg: string;
  consumed_cost_kes: string;
  purchased_kg: string;
  wasted_kg: string;
}

export interface FeedTypeBreakdown {
  feed_type: string;
  consumed_kg: string;
  consumed_cost_kes: string;
  pct_of_total?: string | null;
}

export interface FeedSupplierSpend {
  supplier_id?: string | null;
  supplier_name: string;
  total_kg: string;
  total_cost_kes: string;
  purchase_count: number;
}

export interface FeedFlockCost {
  flock_id: string;
  flock_name: string;
  consumed_kg: string;
  feed_cost_kes: string;
  live_birds: number;
  cost_per_bird_kes?: string | null;
  eggs_collected: number;
  cost_per_egg_kes?: string | null;
  weight_gain_kg?: string | null;
  fcr?: string | null;
  cost_per_kg_gain_kes?: string | null;
}

export interface FeedExpiryAlert {
  item_id: string;
  feed_type: string;
  location: string;
  batch_number?: string | null;
  quantity_kg: string;
  expiry_date: string;
  days_to_expiry: number;
  is_expired: boolean;
}

export interface FeedTopFlock {
  flock_id: string;
  flock_name: string;
  consumed_kg: string;
  feed_cost_kes: string;
}

export interface FeedForecastItem {
  item_id: string;
  feed_type: string;
  location: string;
  quantity_kg: string;
  avg_daily_consumption_kg: string;
  days_remaining?: number | null;
  depletion_date?: string | null;
  recommended_purchase_date?: string | null;
  reorder_level_kg?: string | null;
  status: "ok" | "reorder_soon" | "critical" | "depleting" | "no_data";
}

export interface FeedForecast {
  window_days: number;
  lead_time_days: number;
  items: FeedForecastItem[];
  soonest_depletion_date?: string | null;
  next_purchase_date?: string | null;
  items_needing_purchase: number;
}

export interface FeedAnalytics {
  window_days: number;
  total_consumed_kg: string;
  total_consumed_cost_kes: string;
  total_wasted_kg: string;
  wastage_pct?: string | null;
  avg_cost_per_kg?: string | null;
  usage_trend: FeedUsagePoint[];
  by_feed_type: FeedTypeBreakdown[];
  by_supplier: FeedSupplierSpend[];
  by_flock: FeedFlockCost[];
}
