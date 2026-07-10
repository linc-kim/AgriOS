/**
 * Greena Screen O-02 — Name Entry (Onboarding Step 1)
 * Collects the farmer's name after first login.
 */

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authAPI } from "@/api/auth";
import { queryKeys } from "@/lib/queryClient";

const schema = z.object({
  full_name: z
    .string()
    .min(2, "Name must be at least 2 characters")
    .max(100, "Name is too long"),
});

type FormData = z.infer<typeof schema>;

export default function OnboardingNameScreen() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { register, handleSubmit, formState: { errors } } = useForm<FormData>({
    resolver: zodResolver(schema),
  });

  const mutation = useMutation({
    mutationFn: (data: FormData) => authAPI.updateMe({ full_name: data.full_name }),
    onSuccess: (user) => {
      queryClient.setQueryData(queryKeys.me, user);
      navigate("/set-pin");
    },
  });

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-2xl font-bold text-gray-900">What's your name?</h2>
        <p className="text-gray-500 mt-1">
          This is how you'll appear on Greena
        </p>
      </div>

      <form
        onSubmit={handleSubmit((data) => mutation.mutate(data))}
        className="space-y-6"
      >
        <div>
          <label
            htmlFor="name"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Full name
          </label>
          <input
            id="name"
            type="text"
            autoFocus
            autoComplete="name"
            placeholder="e.g. John Kamau"
            className={`
              w-full h-12 px-4 rounded-xl border text-gray-900 text-base
              placeholder:text-gray-400 outline-none transition-colors
              ${errors.full_name
                ? "border-red-400 focus:border-red-500"
                : "border-gray-200 focus:border-brand-500"
              }
            `}
            {...register("full_name")}
          />
          {errors.full_name && (
            <p className="text-red-500 text-sm mt-1">
              {errors.full_name.message}
            </p>
          )}
        </div>

        <button
          type="submit"
          disabled={mutation.isPending}
          className="
            w-full h-14 bg-brand-600 text-white rounded-xl font-semibold
            disabled:opacity-60 active:bg-brand-700 transition-colors
          "
        >
          {mutation.isPending ? "Saving..." : "Continue"}
        </button>
      </form>
    </div>
  );
}
