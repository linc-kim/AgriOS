/**
 * AGRIOS Screen P-03 — OTP Verification
 * 6-cell input, countdown timer (10 min), resend button (2 min cooldown).
 */

import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authAPI } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";

const OTP_LENGTH = 6;
const RESEND_COOLDOWN_SECONDS = 120;

export default function OTPScreen() {
  const [searchParams] = useSearchParams();
  const phone = searchParams.get("phone") ?? "";
  const navigate = useNavigate();
  const { setAuth } = useAuthStore();

  const [digits, setDigits] = useState<string[]>(Array(OTP_LENGTH).fill(""));
  const [error, setError] = useState<string | null>(null);
  const [resendCountdown, setResendCountdown] = useState(RESEND_COOLDOWN_SECONDS);
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  // Countdown for resend button
  useEffect(() => {
    if (resendCountdown <= 0) return;
    const timer = setInterval(() => {
      setResendCountdown((prev) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(timer);
  }, [resendCountdown]);

  const verifyMutation = useMutation({
    mutationFn: (code: string) =>
      authAPI.verifyOTP({ phone, code }),
    onSuccess: async (data) => {
      useAuthStore.getState().setAccessToken(data.access_token);
      const user = await authAPI.getMe();
      setAuth(data.access_token, user);
      if (data.is_new_user || !data.has_pin) {
        navigate("/onboarding/name");
      } else {
        navigate("/");
      }
    },
    onError: (err: any) => {
      const code = err?.response?.data?.error?.code;
      if (code === "OTP_EXPIRED") {
        setError("Code has expired. Request a new one.");
      } else if (code === "OTP_MAX_ATTEMPTS") {
        setError("Too many wrong attempts. Request a new code.");
      } else {
        setError("Incorrect code. Try again.");
      }
      // Clear inputs on error
      setDigits(Array(OTP_LENGTH).fill(""));
      inputRefs.current[0]?.focus();
    },
  });

  const resendMutation = useMutation({
    mutationFn: () => authAPI.requestOTP({ phone }),
    onSuccess: () => {
      setResendCountdown(RESEND_COOLDOWN_SECONDS);
      setError(null);
      setDigits(Array(OTP_LENGTH).fill(""));
      inputRefs.current[0]?.focus();
    },
  });

  function handleDigitChange(index: number, value: string) {
    if (!value.match(/^\d?$/)) return;
    const newDigits = [...digits];
    newDigits[index] = value;
    setDigits(newDigits);
    setError(null);

    if (value && index < OTP_LENGTH - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    // Auto-submit when all digits are filled
    if (value && newDigits.every(Boolean)) {
      verifyMutation.mutate(newDigits.join(""));
    }
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent) {
    if (e.key === "Backspace" && !digits[index] && index > 0) {
      inputRefs.current[index - 1]?.focus();
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Enter code</h2>
        <p className="text-gray-500 mt-1">
          We sent a 6-digit code to{" "}
          <span className="text-gray-700 font-medium">{phone}</span>
        </p>
      </div>

      {/* 6-cell OTP input */}
      <div className="flex gap-3 justify-center">
        {digits.map((digit, index) => (
          <input
            key={index}
            ref={(el) => { inputRefs.current[index] = el; }}
            type="text"
            inputMode="numeric"
            maxLength={1}
            value={digit}
            onChange={(e) => handleDigitChange(index, e.target.value)}
            onKeyDown={(e) => handleKeyDown(index, e)}
            className={`
              w-12 h-14 text-center text-xl font-bold rounded-xl border-2
              outline-none transition-colors
              ${error
                ? "border-red-400 text-red-600"
                : digit
                  ? "border-brand-500 text-brand-700"
                  : "border-gray-200 text-gray-900"
              }
            `}
            autoFocus={index === 0}
          />
        ))}
      </div>

      {error && (
        <p className="text-red-500 text-sm text-center">{error}</p>
      )}

      {verifyMutation.isPending && (
        <p className="text-gray-500 text-sm text-center">Verifying...</p>
      )}

      {/* Resend */}
      <div className="text-center">
        {resendCountdown > 0 ? (
          <p className="text-gray-400 text-sm">
            Resend in {Math.floor(resendCountdown / 60)}:
            {String(resendCountdown % 60).padStart(2, "0")}
          </p>
        ) : (
          <button
            onClick={() => resendMutation.mutate()}
            disabled={resendMutation.isPending}
            className="text-brand-600 font-medium text-sm disabled:opacity-50"
          >
            {resendMutation.isPending ? "Sending..." : "Resend code"}
          </button>
        )}
      </div>

      <button
        onClick={() => navigate("/login")}
        className="w-full text-gray-500 text-sm text-center"
      >
        Wrong number? Change it
      </button>
    </div>
  );
}
