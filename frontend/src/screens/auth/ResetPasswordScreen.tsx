/**
 * Greena — Reset password (from the emailed link).
 *
 * Reads the single-use token from the URL (?token=...), takes a new password,
 * and posts to /auth/reset-password. On success every existing session is
 * revoked server-side, so the user logs in fresh. Handles a missing, invalid or
 * expired token with a clear route back to requesting a new link.
 */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Lock, ArrowRight, AlertCircle, CheckCircle2 } from "lucide-react";

import { authAPI } from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";

const schema = z
  .object({
    password: z
      .string()
      .min(12, "Use at least 12 characters")
      .max(200, "That password is too long"),
    confirm: z.string().min(1, "Please confirm your password"),
  })
  .refine((d) => d.password === d.confirm, {
    message: "Passwords do not match",
    path: ["confirm"],
  });
type FormData = z.infer<typeof schema>;

export default function ResetPasswordScreen() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [done, setDone] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (data: FormData) =>
      authAPI.resetPassword({ token, new_password: data.password }),
    onSuccess: () => setDone(true),
    onError: (err: any) => {
      const status = err?.response?.status;
      // A bad or expired reset token comes back as 401 UNAUTHENTICATED (or 400).
      const invalidToken = status === 401 || status === 400;
      setFormError(
        invalidToken
          ? "This reset link is invalid or has expired. Request a new one below."
          : "Something went wrong. Please try again.",
      );
    },
  });

  // No token in the link at all.
  if (!token) {
    return (
      <div className="space-y-6 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600">
          <AlertCircle className="h-6 w-6" />
        </span>
        <div>
          <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
            This link looks incomplete
          </h2>
          <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-gray-500">
            The reset link is missing its code. Please request a fresh one.
          </p>
        </div>
        <Link to="/forgot-password" className="inline-block font-semibold text-brand-600 hover:text-brand-700">
          Request a new reset link
        </Link>
      </div>
    );
  }

  if (done) {
    return (
      <div className="space-y-6 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <CheckCircle2 className="h-6 w-6" />
        </span>
        <div>
          <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
            Password updated
          </h2>
          <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-gray-500">
            Your password has been changed and you've been signed out everywhere.
            Log in with your new password.
          </p>
        </div>
        <Link
          to="/login"
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-3 text-sm font-semibold text-white hover:bg-brand-700"
        >
          Log in <ArrowRight className="h-4 w-4" />
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <div>
        <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
          Set a new password
        </h2>
        <p className="mt-1.5 text-[15px] text-gray-500">
          Choose a strong password you don't use anywhere else.
        </p>
      </div>

      {formError && (
        <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-red-100 bg-red-50 px-3.5 py-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            {formError}{" "}
            <Link to="/forgot-password" className="font-semibold underline">
              Request a new link
            </Link>
          </span>
        </div>
      )}

      <form
        onSubmit={handleSubmit((d) => {
          setFormError(null);
          mutation.mutate(d);
        })}
        className="space-y-4"
        noValidate
      >
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          autoFocus
          placeholder="At least 12 characters"
          leftIcon={<Lock className="h-[18px] w-[18px]" />}
          error={errors.password?.message}
          {...register("password")}
        />
        <TextField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          placeholder="Type it again"
          leftIcon={<Lock className="h-[18px] w-[18px]" />}
          error={errors.confirm?.message}
          {...register("confirm")}
        />
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending} rightIcon={<ArrowRight className="h-4 w-4" />} className="mt-1">
          Update password
        </Button>
      </form>

      <p className="text-center text-sm text-gray-500">
        <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700">
          Back to log in
        </Link>
      </p>
    </div>
  );
}
