/**
 * Greena — Onboarding wizard (Welcome → Organization → Farm → Dashboard).
 * Autosaves to localStorage, supports back navigation, and creates the
 * organization + first farm against the live backend on finish.
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, ArrowLeft, Check, AlertCircle, Sprout, Building2 } from "lucide-react";

import { organizationsAPI } from "@/api/organizations";
import { createFarm } from "@/api/farms";
import { useAuthStore } from "@/stores/authStore";
import { Logo } from "@/components/ui/Logo";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";
import { Select, type SelectOption } from "@/components/ui/Select";

const STORAGE_KEY = "greena-onboarding";

const COUNTRIES: SelectOption[] = [
  { value: "KE", label: "Kenya" },
  { value: "UG", label: "Uganda" },
  { value: "TZ", label: "Tanzania" },
  { value: "RW", label: "Rwanda" },
  { value: "NG", label: "Nigeria" },
  { value: "ZA", label: "South Africa" },
];
const CURRENCIES: SelectOption[] = [
  { value: "KES", label: "KES — Kenyan Shilling" },
  { value: "UGX", label: "UGX — Ugandan Shilling" },
  { value: "TZS", label: "TZS — Tanzanian Shilling" },
  { value: "NGN", label: "NGN — Nigerian Naira" },
  { value: "USD", label: "USD — US Dollar" },
];
const TIMEZONES: SelectOption[] = [
  { value: "Africa/Nairobi", label: "Africa/Nairobi (EAT)" },
  { value: "Africa/Kampala", label: "Africa/Kampala (EAT)" },
  { value: "Africa/Dar_es_Salaam", label: "Africa/Dar es Salaam (EAT)" },
  { value: "Africa/Lagos", label: "Africa/Lagos (WAT)" },
  { value: "Africa/Johannesburg", label: "Africa/Johannesburg (SAST)" },
];
const FARM_TYPES: SelectOption[] = [
  { value: "poultry", label: "Poultry" },
  { value: "dairy", label: "Dairy" },
  { value: "crops", label: "Crops" },
  { value: "mixed", label: "Mixed" },
  { value: "other", label: "Other" },
];

interface Draft {
  orgName: string;
  country: string;
  currency: string;
  timezone: string;
  farmName: string;
  farmType: string;
  location: string;
}

const EMPTY: Draft = {
  orgName: "",
  country: "KE",
  currency: "KES",
  timezone: "Africa/Nairobi",
  farmName: "",
  farmType: "poultry",
  location: "",
};

export default function OnboardingScreen() {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<Draft>(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      return saved ? { ...EMPTY, ...JSON.parse(saved) } : EMPTY;
    } catch {
      return EMPTY;
    }
  });
  const [error, setError] = useState<string | null>(null);

  // Autosave
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  }, [draft]);

  const set = (patch: Partial<Draft>) => setDraft((d) => ({ ...d, ...patch }));

  const finish = useMutation({
    mutationFn: async () => {
      const org = await organizationsAPI.create({
        name: draft.orgName.trim(),
        country: draft.country,
        currency: draft.currency,
        timezone: draft.timezone,
      });
      const typeLabel = FARM_TYPES.find((t) => t.value === draft.farmType)?.label;
      await createFarm({
        name: draft.farmName.trim(),
        description: typeLabel ? `${typeLabel} farm` : undefined,
        location: draft.location.trim() || undefined,
        organization_id: org.id,
      });
      localStorage.removeItem(STORAGE_KEY);
    },
    onSuccess: () => navigate("/", { replace: true }),
    onError: () => setError("We couldn't finish setup. Please try again."),
  });

  const orgValid = draft.orgName.trim().length >= 2;
  const farmValid = draft.farmName.trim().length >= 2;

  const next = () => {
    setError(null);
    if (step === 1 && !orgValid) return setError("Please enter an organization name.");
    if (step === 2) {
      if (!farmValid) return setError("Please enter a farm name.");
      finish.mutate();
      return;
    }
    setStep((s) => Math.min(s + 1, 2));
  };
  const back = () => {
    setError(null);
    setStep((s) => Math.max(s - 1, 0));
  };

  const progress = useMemo(() => (step / 2) * 100, [step]);

  return (
    <div className="flex min-h-[100dvh] flex-col bg-[#f7faf6]">
      {/* Top bar with progress */}
      <header className="border-b border-gray-100 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-5 py-4">
          <Logo variant="lockup" className="h-7 w-auto" />
          {step > 0 && (
            <span className="text-xs font-medium tracking-wide text-gray-400">
              Step {step} of 2
            </span>
          )}
        </div>
        <div className="h-0.5 w-full bg-gray-100">
          <div
            className="h-full bg-brand-600 transition-[width] duration-500 ease-[cubic-bezier(.16,1,.3,1)]"
            style={{ width: `${progress}%` }}
          />
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-5 py-12">
        <div key={step} className="animate-[ob-in_.4s_cubic-bezier(.16,1,.3,1)]">
          {error && (
            <div
              role="alert"
              className="mb-5 flex items-start gap-2.5 rounded-xl border border-red-100 bg-red-50 px-3.5 py-3 text-sm text-red-700"
            >
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {step === 0 && (
            <div className="text-center">
              <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50">
                <Sprout className="h-7 w-7 text-brand-600" />
              </div>
              <h1 className="text-[1.7rem] font-semibold tracking-[-0.02em] text-gray-900">
                Welcome to Greena{user?.full_name ? `, ${user.full_name.split(" ")[0]}` : ""}
              </h1>
              <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-gray-500">
                Let's set up your workspace. It takes about a minute — create your
                organization, then your first farm.
              </p>
            </div>
          )}

          {step === 1 && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50">
                  <Building2 className="h-5 w-5 text-brand-600" />
                </span>
                <div>
                  <h1 className="text-xl font-semibold tracking-[-0.02em] text-gray-900">
                    Your organization
                  </h1>
                  <p className="text-sm text-gray-500">The workspace that owns your farms.</p>
                </div>
              </div>
              <TextField
                label="Organization name"
                autoFocus
                placeholder="Sunrise Farms Ltd"
                value={draft.orgName}
                onChange={(e) => set({ orgName: e.target.value })}
              />
              <Select
                label="Country"
                options={COUNTRIES}
                value={draft.country}
                onChange={(e) => set({ country: e.target.value })}
              />
              <div className="grid grid-cols-2 gap-3">
                <Select
                  label="Currency"
                  options={CURRENCIES}
                  value={draft.currency}
                  onChange={(e) => set({ currency: e.target.value })}
                />
                <Select
                  label="Timezone"
                  options={TIMEZONES}
                  value={draft.timezone}
                  onChange={(e) => set({ timezone: e.target.value })}
                />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-5">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand-50">
                  <Sprout className="h-5 w-5 text-brand-600" />
                </span>
                <div>
                  <h1 className="text-xl font-semibold tracking-[-0.02em] text-gray-900">
                    Your first farm
                  </h1>
                  <p className="text-sm text-gray-500">You can add more farms later.</p>
                </div>
              </div>
              <TextField
                label="Farm name"
                autoFocus
                placeholder="Green Acres"
                value={draft.farmName}
                onChange={(e) => set({ farmName: e.target.value })}
              />
              <Select
                label="Farm type"
                options={FARM_TYPES}
                value={draft.farmType}
                onChange={(e) => set({ farmType: e.target.value })}
              />
              <TextField
                label="Location"
                hint="Optional — town, county, or a short description."
                placeholder="Nakuru, Kenya"
                value={draft.location}
                onChange={(e) => set({ location: e.target.value })}
              />
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="mt-8 flex items-center gap-3">
          {step > 0 && (
            <Button
              variant="secondary"
              size="lg"
              onClick={back}
              disabled={finish.isPending}
              leftIcon={<ArrowLeft className="h-4 w-4" />}
            >
              Back
            </Button>
          )}
          <Button
            size="lg"
            fullWidth
            onClick={next}
            loading={finish.isPending}
            rightIcon={
              step === 2 ? <Check className="h-4 w-4" /> : <ArrowRight className="h-4 w-4" />
            }
          >
            {step === 0 ? "Get started" : step === 2 ? "Finish setup" : "Continue"}
          </Button>
        </div>
      </main>
    </div>
  );
}
