/**
 * Greena — PIN Login Screen
 * For returning users who have set a PIN.
 */

import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authAPI } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

export default function PINLoginScreen() {
  const [searchParams] = useSearchParams();
  const phone = searchParams.get("phone") ?? "";
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (pin: string) => authAPI.verifyPIN({ phone, pin }),
    onSuccess: async (data) => {
      useAuthStore.getState().setAccessToken(data.access_token);
      const user = await authAPI.getMe();
      setAuth(data.access_token, user);
      navigate("/");
    },
    onError: () => {
      setError("Incorrect PIN. Try again.");
      setValue("");
    },
  });

  function handleInput(digit: string) {
    if (digit === "DEL") {
      setValue((prev) => prev.slice(0, -1));
      setError(null);
      return;
    }
    if (value.length >= 6) return;
    const next = value + digit;
    setValue(next);
    if (next.length === 6) {
      mutation.mutate(next);
    }
  }

  const KEYPAD = [
    ["1", "2", "3"],
    ["4", "5", "6"],
    ["7", "8", "9"],
    ["", "0", "DEL"],
  ];

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Enter PIN</h2>
        <p className="text-gray-500 mt-1">Welcome back</p>
      </div>

      {/* PIN dots */}
      <div className="flex justify-center gap-4">
        {Array(6).fill(null).map((_, i) => (
          <div
            key={i}
            className={`w-3 h-3 rounded-full transition-colors ${
              i < value.length ? "bg-brand-600" : "bg-gray-200"
            }`}
          />
        ))}
      </div>

      {error && <p className="text-red-500 text-sm text-center">{error}</p>}
      {mutation.isPending && (
        <p className="text-gray-400 text-sm text-center">Verifying...</p>
      )}

      {/* Keypad */}
      <div className="grid grid-cols-3 gap-3 max-w-xs mx-auto">
        {KEYPAD.flat().map((key, i) => (
          <button
            key={i}
            onClick={() => key && handleInput(key)}
            disabled={!key || mutation.isPending}
            className={`
              h-16 rounded-2xl text-xl font-semibold transition-colors
              disabled:opacity-0 active:scale-95
              ${key === "DEL"
                ? "bg-gray-100 text-gray-600 text-base"
                : "bg-gray-100 text-gray-900"
              }
            `}
          >
            {key}
          </button>
        ))}
      </div>

      <button
        onClick={() => navigate("/login")}
        className="w-full text-brand-600 font-medium text-sm text-center"
      >
        Use OTP instead
      </button>
    </div>
  );
}
