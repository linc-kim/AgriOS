/**
 * Greena — Module registry.
 * The single source of truth the shell renders from: navigation, routing,
 * breadcrumbs, and the command palette all derive from this list. New modules
 * register here — the shell never needs redesigning.
 */
import type { ComponentType } from "react";
import type { LucideIcon } from "lucide-react";
import {
  LayoutDashboard,
  Bird,
  Sprout,
  Package,
  Wheat,
  Wallet,
  BarChart3,
  FileText,
  Store,
  Zap,
  Settings,
  CreditCard,
  ShieldCheck,
  Rocket,
} from "lucide-react";
import { AriaIcon } from "@/components/aria";

export type ModuleSection = "main" | "insights" | "platform" | "system";

/**
 * Nav icons are lucide glyphs with one exception: ARIA brings its own mark.
 * Widened to any component taking `className`, which is the only contract the
 * shell relies on — every render site is `<Icon className="h-4 w-4" />`.
 */
export type ModuleIcon = LucideIcon | ComponentType<{ className?: string }>;

export interface ModuleDef {
  id: string;
  label: string;
  path: string;
  icon: ModuleIcon;
  section: ModuleSection;
  /** A one-line purpose, shown in the module's empty state + command palette. */
  description: string;
  /** True once the module has a real screen (otherwise it renders an empty state). */
  ready?: boolean;
  adminOnly?: boolean;
}

export const MODULES: ModuleDef[] = [
  { id: "dashboard", label: "Dashboard", path: "/dashboard", icon: LayoutDashboard, section: "main", ready: true, description: "Your farm at a glance." },
  { id: "livestock", label: "Livestock", path: "/livestock", icon: Bird, section: "main", ready: true, description: "Track flocks, mortality, weights and vaccinations." },
  { id: "crops", label: "Crops", path: "/crops", icon: Sprout, section: "main", description: "Plan plantings, monitor growth and harvests." },
  { id: "feed", label: "Feed", path: "/feed", icon: Wheat, section: "main", ready: true, description: "Feed stock, purchases, consumption and cost." },
  { id: "inventory", label: "Inventory & Assets", path: "/inventory", icon: Package, section: "main", ready: true, description: "Store items, stock movements, suppliers, assets and maintenance." },
  { id: "finance", label: "Finance", path: "/finance", icon: Wallet, section: "insights", ready: true, description: "Expenses, revenue and profitability." },
  { id: "analytics", label: "Analytics", path: "/analytics", icon: BarChart3, section: "insights", description: "Trends and performance across your operation." },
  { id: "reports", label: "Reports", path: "/reports", icon: FileText, section: "insights", ready: true, description: "Reports, dashboards, comparisons and exports." },
  // Named for the assistant, not the technology. "AI Assistant" described the
  // category; ARIA is who the farmer actually asks.
  { id: "ai", label: "ARIA", path: "/ai", icon: AriaIcon, section: "insights", ready: true, description: "Predictions, forecasts and an assistant grounded in your farm." },
  { id: "marketplace", label: "Marketplace", path: "/marketplace", icon: Store, section: "platform", description: "Market prices and trusted suppliers." },
  { id: "automation", label: "Automation", path: "/automation", icon: Zap, section: "platform", ready: true, description: "Triggers, rules, reminders and your activity center." },
  { id: "production", label: "Production", path: "/production", icon: Rocket, section: "platform", ready: true, description: "System status, diagnostics, backups, imports, exports and release readiness." },
  { id: "settings", label: "Settings", path: "/settings", icon: Settings, section: "system", description: "Organization, farm and account settings." },
  { id: "billing", label: "Billing", path: "/billing", icon: CreditCard, section: "system", description: "Your plan and invoices." },
  { id: "admin", label: "Administration", path: "/admin", icon: ShieldCheck, section: "system", ready: true, adminOnly: true, description: "Platform administration." },
];

export const SECTIONS: { id: ModuleSection; label: string }[] = [
  { id: "main", label: "Workspace" },
  { id: "insights", label: "Insights" },
  { id: "platform", label: "Platform" },
  { id: "system", label: "Account" },
];

export const moduleByPath = (path: string): ModuleDef | undefined =>
  MODULES.find((m) => m.path === path);
