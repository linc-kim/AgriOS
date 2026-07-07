/**
 * Greena — Create account (email + password), wired to the live backend.
 */
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { Mail, Lock, User as UserIcon, ArrowRight, AlertCircle } from "lucide-react";

import { authAPI } from "@/api/auth";
import { completeAuthAndRoute } from "@/lib/completeAuth";
import { Button } from "@/components/ui/Button";
import { TextField } from "@/components/ui/TextField";

const schema = z.object({
  full_name: z.string().trim().max(120, "That name is too long").optional(),
  email: z.string().min(1, "Email is required").email("Enter a valid email"),
  password: z
    .string()
    .min(12, "Use at least 12 characters")
    .max(200, "That password is too long"),
  remember_me: z.boolean().optional(),
});
type FormData = z.infer<typeof schema>;

export default function SignUpScreen() {
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
      const { access_token } = await authAPI.signup({
        email: data.email,
        password: data.password,
        full_name: data.full_name || undefined,
        remember_me: data.remember_me,
      });
      return completeAuthAndRoute(access_token);
    },
    onSuccess: (dest) => navigate(dest, { replace: true }),
    onError: (err: any) => {
      const code = err?.response?.data?.error?.code;
      const message = err?.response?.data?.error?.message;
      if (code === "CONFLICT") {
        setFormError("An account with this email already exists. Try logging in.");
      } else if (code === "VALIDATION_ERROR") {
        setFormError(message || "Please check your details and try again.");
      } else {
        setFormError("Something went wrong. Please try again.");
      }
    },
  });

  return (
    <div className="space-y-7">
      <div>
        <h2 className="text-[1.6rem] font-semibold tracking-[-0.02em] text-gray-900">
          Create your account
        </h2>
        <p className="mt-1.5 text-[15px] text-gray-500">
          Start running your farm on Greena — free to begin.
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
          label="Full name"
          autoComplete="name"
          autoFocus
          placeholder="Ada Waweru"
          leftIcon={<UserIcon className="h-[18px] w-[18px]" />}
          error={errors.full_name?.message}
          {...register("full_name")}
        />
        <TextField
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@farm.co"
          leftIcon={<Mail className="h-[18px] w-[18px]" />}
          error={errors.email?.message}
          {...register("email")}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="new-password"
          placeholder="Create a strong passphrase"
          hint="At least 12 characters. A memorable phrase works well."
          leftIcon={<Lock className="h-[18px] w-[18px]" />}
          error={errors.password?.message}
          {...register("password")}
        />

        <Button
          type="submit"
          size="lg"
          fullWidth
          loading={mutation.isPending}
          rightIcon={<ArrowRight className="h-4 w-4" />}
          className="mt-1"
        >
          Create account
        </Button>
      </form>

      <p className="text-center text-sm text-gray-500">
        Already have an account?{" "}
        <Link to="/login" className="font-semibold text-brand-600 hover:text-brand-700">
          Log in
        </Link>
      </p>
    </div>
  );
}
