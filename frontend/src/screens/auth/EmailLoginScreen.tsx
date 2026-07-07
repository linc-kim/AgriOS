/**
 * Greena — Log in (email + password), wired to the live backend.
 */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Mail, Lock, ArrowRight, AlertCircle } from "lucide-react";

import { authAPI } from "@/api/auth";
import { completeAuthAndRoute } from "@/lib/completeAuth";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";

const schema = z.object({
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z.string().min(1, "Password is required"),
  remember_me: z.boolean().optional(),
});
type FormData = z.infer<typeof schema>;

export default function EmailLoginScreen() {
  const navigate = useNavigate();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<FormData>({
    resolver: zodResolver(schema),
    defaultValues: { remember_me: true },
  });

  const mutation = useMutation({
    mutationFn: async (data: FormData) => {
      const { access_token } = await authAPI.login({
        email: data.email,
        password: data.password,
        remember_me: data.remember_me,
      });
      return completeAuthAndRoute(access_token);
    },
    onSuccess: (dest) => navigate(dest, { replace: true }),
    onError: (err: any) => {
      const code = err?.response?.data?.error?.code;
      setFormError(
        code === "UNAUTHENTICATED"
          ? "Incorrect email or password."
          : "Something went wrong. Please try again.",
      );
    },
  });

  return (
    <div className="space-y-7">
      <div>
        <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
          Welcome back
        </h2>
        <p className="mt-1.5 text-[15px] text-gray-500">
          Log in to your Greena workspace.
        </p>
      </div>

      {formError && (
        <div
          role="alert"
          className="flex items-start gap-2.5 rounded-xl border border-red-100 bg-red-50 px-3.5 py-3 text-sm text-red-700"
        >
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
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="Your password"
          leftIcon={<Lock className="h-[18px] w-[18px]" />}
          error={errors.password?.message}
          {...register("password")}
        />

        <label className="flex cursor-pointer select-none items-center gap-2.5 pt-0.5 text-sm text-gray-600">
          <input
            type="checkbox"
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500/30"
            {...register("remember_me")}
          />
          Keep me signed in
        </label>

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={mutation.isPending}
          rightIcon={<ArrowRight className="h-4 w-4" />}
          className="mt-1"
        >
          Log in
        </Button>
      </form>

      <p className="text-center text-sm text-gray-500">
        New to Greena?{" "}
        <Link to="/signup" className="font-semibold text-brand-600 hover:text-brand-700">
          Create an account
        </Link>
      </p>
    </div>
  );
}
