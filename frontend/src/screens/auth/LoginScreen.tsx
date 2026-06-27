/**
 * AGRIOS Screen P-02 — Login
 * Phone number entry. Triggers OTP request.
 * Supports +254, 07, and 01 formats.
 */

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { authAPI } from "@/api/auth";
import { useMutation } from "@tanstack/react-query";

const schema = z.object({
  phone: z
    .string()
    .min(1, "Phone number is required")
    .regex(
      /^(\+?254|0)[17]\d{8}$/,
      "Enter a valid Kenyan phone number (e.g. 0712345678)",
    ),
});

type FormData = z.infer<typeof schema>;

export default function LoginScreen() {
  const navigate = useNavigate();

  const {
    register,
    handleSubmit,
    formState: { errors },
    setError,
  } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) => authAPI.requestOTP({ phone: data.phone }),
    onSuccess: (_, variables) => {
      // Pass phone to OTP screen via URL param
      navigate(`/verify-otp?phone=${encodeURIComponent(variables.phone)}`);
    },
    onError: (error: any) => {
      const code = error?.response?.data?.error?.code;
      if (code === "RATE_LIMITED") {
        setError("phone", {
          message: "Too many requests. Please wait 10 minutes.",
        });
      } else {
        setError("phone", { message: "Something went wrong. Try again." });
      }
    },
  });

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Welcome back</h2>
        <p className="text-gray-500 mt-1">Enter your phone number to continue</p>
      </div>

      <form onSubmit={handleSubmit((data) => mutation.mutate(data))} className="space-y-4">
        <div>
          <label
            htmlFor="phone"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Phone number
          </label>
          <input
            id="phone"
            type="tel"
            inputMode="tel"
            placeholder="0712 345 678"
            autoComplete="tel"
            autoFocus
            className={`
              w-full h-12 px-4 rounded-xl border text-gray-900 text-base
              placeholder:text-gray-400 outline-none transition-colors
              ${errors.phone
                ? "border-red-400 focus:border-red-500"
                : "border-gray-200 focus:border-brand-500"
              }
            `}
            {...register("phone")}
          />
          {errors.phone && (
            <p className="text-red-500 text-sm mt-1">{errors.phone.message}</p>
          )}
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="
            w-full h-14 bg-brand-600 text-white rounded-xl font-semibold text-base
            disabled:opacity-60 active:bg-brand-700 transition-colors
            flex items-center justify-center gap-2
          "
        >
          {mutation.isPending ? (
            <>
              <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              Sending code...
            </>
          ) : (
            "Send code"
          )}
        </button>
      </form>

      <p className="text-xs text-center text-gray-400">
        By continuing, you agree to AGRIOS Terms of Service
      </p>
    </div>
  );
}
