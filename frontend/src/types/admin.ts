/**
 * Greena — Admin Platform types (Module 10).
 */

export interface AdminDashboardData {
  organizations: number;
  farms: number;
  users: number;
  active_users_today: number;
  monthly_revenue_estimate: string;
  ai_requests_total: number;
  suspended_orgs: number;
  suspended_users: number;
  maintenance_mode: boolean;
  health_status: string;
  jobs_failed_24h: number;
}
export interface AdminOrgRow {
  id: string; name: string; slug: string; owner_name: string | null;
  country: string | null; currency: string; is_suspended: boolean; is_deleted: boolean;
  farm_count: number; member_count: number; plan_name: string | null; created_at: string;
}
export interface AdminOrgDetail extends AdminOrgRow {
  flock_count: number; active_flock_count: number; ai_requests: number;
  total_revenue: string; total_expenses: string;
}
export interface AdminUserRow {
  id: string; full_name: string | null; email: string | null; phone: string | null;
  roles: string[]; is_active: boolean; is_suspended: boolean; last_login_at: string | null; created_at: string;
}
export interface AdminFarmRow {
  id: string; name: string; county: string | null; owner_name: string | null;
  is_active: boolean; is_archived: boolean; flock_count: number; member_count: number; created_at: string;
}
export interface AdminAuditRow {
  id: string; action: string; resource_type: string; resource_id: string | null;
  user_id: string | null; actor_name: string | null; farm_id: string | null;
  ip_address: string | null; old_value: Record<string, any> | null; new_value: Record<string, any> | null; created_at: string;
}
export interface AdminPage<T> { items: T[]; total: number; page: number; page_size: number; }
export interface SubscriptionBreakdown { plan: string; farm_count: number; monthly_revenue: string; }
export interface AdminGrowthPoint { period: string; organizations: number; farms: number; users: number; }
export interface AdminTopFarm { farm_id: string; name: string; ai_requests: number; }
export interface PlatformAnalytics {
  total_organizations: number; total_farms: number; total_users: number; active_users_today: number;
  api_requests_estimate: number; storage_mb_estimate: string; ai_requests_total: number;
  ai_gemini: number; ai_claude: number; ai_offline: number; monthly_revenue_estimate: string;
  subscription_breakdown: SubscriptionBreakdown[]; growth: AdminGrowthPoint[]; top_farms: AdminTopFarm[];
}
export interface FeatureFlagRow {
  id: string; flag_key: string; name: string; description: string | null;
  is_enabled: boolean; organization_id: string | null; created_at: string; updated_at: string;
}
export interface SystemConfigData {
  maintenance_mode: boolean; read_only_mode: boolean; banner_message: string | null;
  maintenance_scheduled_at: string | null; ai_provider_priority: string[]; email_sender: string;
  sms_sender: string; default_currency: string; default_timezone: string; data_retention_days: number;
  limits: Record<string, any>; updated_at: string;
}
export interface HealthComponent { name: string; status: string; detail: string | null; }
export interface SystemHealthData {
  status: string; version: string; environment: string; uptime_seconds: number;
  components: HealthComponent[]; checked_at: string;
}
export interface BackgroundJobRow {
  id: string; name: string; status: string; queue: string; started_at: string | null;
  finished_at: string | null; duration_ms: number | null; attempts: number; error: string | null;
  result: Record<string, any>; created_at: string; updated_at: string;
}
export interface BackgroundJobStats {
  total: number; success: number; failed: number; running: number; queued: number;
  queue_depth: number; avg_duration_ms: number | null; recent: BackgroundJobRow[];
}
export interface AdminAskResponse { answer: string; provider: string; sources: string[]; }
