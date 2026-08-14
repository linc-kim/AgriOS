/**
 * Greena — Forgot password (request a reset link).
 *
 * Posts to /auth/forgot-password, which always reports success (it never
 * reveals whether an address is registered). So we show the same "check your
 * email" confirmation either way.
 */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Mail, ArrowRight, AlertCircle, MailCheck } from "lucide-react";

import { authAPI } from "@/api/auth";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
});
type FormData = z.infer<typeof schema>;

export default function ForgotPasswordScreen() {
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    getValues,
    formState: { errors },
  } = useForm<FormData>({ resolver: zodResolver(schema) });

  const mutation = useMutation({
    mutationFn: (data: FormData) => authAPI.forgotPassword(data.email),
    onSuccess: () => setSent(true),
    onError: () => setFormError("Something went wrong. Please try again."),
  });

  if (sent) {
    return (
      <div className="space-y-6 text-center">
        <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-brand-50 text-brand-600">
          <MailCheck className="h-6 w-6" />
        </span>
        <div>
          <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
            Check your email
          </h2>
          <p className="mx-auto mt-2 max-w-sm text-[15px] leading-relaxed text-gray-500">
            If an account exists for <span className="font-medium text-gray-700">{getValues("email")}</span>,
            a link to reset your password is on its way. It expires in a few hours.
          </p>
        </div>
        <p className="text-sm text-gray-500">
          Didn't get it? Check spam, or{" "}
          <button
            type="button"
            onClick={() => mutation.mutate({ email: getValues("email") })}
            className="font-semibold text-brand-600 hover:text-brand-700"
          >
            send it again
          </button>
          .
        </p>
        <p className="text-sm text-gray-500">
          <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700">
            Back to log in
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-7">
      <div>
        <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
          Forgot your password?
        </h2>
        <p className="mt-1.5 text-[15px] text-gray-500">
          No problem. Enter your email and we'll send you a link to set a new one.
        </p>
      </div>

      {formError && (
        <div role="alert" className="flex items-start gap-2.5 rounded-xl border border-red-100 bg-red-50 px-3.5 py-3 text-sm text-red-700">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{formError}</span>
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
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          autoFocus
          placeholder="you@farm.co"
          leftIcon={<Mail className="h-[18px] w-[18px]" />}
          error={errors.email?.message}
          {...register("email")}
        />
        <Button type="submit" size="lg" fullWidth loading={mutation.isPending} rightIcon={<ArrowRight className="h-4 w-4" />} className="mt-1">
          Send reset link
        </Button>
      </form>

      <p className="text-center text-sm text-gray-500">
        Remembered it?{" "}
        <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700">
          Back to log in
        </Link>
      </p>
    </div>
  );
}
