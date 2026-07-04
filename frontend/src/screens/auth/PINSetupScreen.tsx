/**
 * AGRIOS Screen P-04 — PIN Setup
 * First-time PIN creation. 4–6 digit numeric PIN.
 */

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authAPI } from "@/api/auth";

type Step = "create" | "confirm";

export default function PINSetupScreen() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("create");
  const [pin, setPin] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (data: { pin: string; pin_confirm: string }) =>
      authAPI.setPIN(data),
    onSuccess: () => {
      navigate("/onboarding/name");
    },
    onError: () => {
      setError("Could not set PIN. Please try again.");
    },
  });

  function handlePinSubmit(value: string) {
    if (step === "create") {
      setPin(value);
      setStep("confirm");
    } else {
      if (value !== pin) {
        setError("PINs don't match. Try again.");
        setStep("create");
        setPin("");
        return;
      }
      mutation.mutate({ pin, pin_confirm: value });
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">
          {step === "create" ? "Create PIN" : "Confirm PIN"}
        </h2>
        <p className="text-gray-500 mt-1">
          {step === "create"
            ? "Set a 4–6 digit PIN for quick login"
            : "Enter the same PIN again to confirm"}
        </p>
      </div>

      <PINInput
        key={step}
        onComplete={handlePinSubmit}
        isLoading={mutation.isPending}
      />

      {error && (
        <p className="text-red-500 text-sm text-center">{error}</p>
      )}
    </div>
  );
}

function PINInput({
  onComplete,
  isLoading,
}: {
  onComplete: (pin: string) => void;
  isLoading?: boolean;
}) {
  const [value, setValue] = useState("");

  function handleInput(digit: string) {
    if (digit === "DEL") {
      setValue((prev) => prev.slice(0, -1));
      return;
    }
    if (value.length >= 6) return;
    const next = value + digit;
    setValue(next);
    if (next.length >= 4) {
      // Auto-submit at 4, 5, or 6 digits (user can press confirm)
    }
  }

  function handleSubmit() {
    if (value.length < 4) return;
    onComplete(value);
    setValue("");
  }

  const KEYPAD = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["DEL", "0", "OK"],
  ];

  return (
    <div className="space-y-6">
      {/* PIN dots */}
      <div className="flex justify-center gap-4">
        {Array(6)
          .fill(null)
          .map((_, i) => (
            <div
              key={i}
              className={`
                w-3 h-3 rounded-full transition-colors
                ${i < value.length ? "bg-brand-600" : "bg-gray-200"}
              `}
            />
          ))}
      </div>

      {/* Keypad */}
      <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto">
        {KEYPAD.flat().map((key) => (
          <button
            key={key}
            onClick={() => {
              if (key === "OK") handleSubmit();
              else handleInput(key);
            }}
            disabled={isLoading || (key === "OK" && value.length < 4)}
            className={`
              h-16 rounded-2xl text-xl font-semibold transition-colors
              disabled:opacity-40 active:scale-95
              ${key === "OK"
                ? "bg-brand-600 text-white"
                : key === "DEL"
                  ? "bg-gray-100 text-gray-600 text-base"
                  : "bg-gray-100 text-gray-900"
              }
            `}
          >
            {key}
          </button>
        ))}
      </div>
    </div>
  );
}
