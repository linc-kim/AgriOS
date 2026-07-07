import { forwardRef, useId, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cn } from "@/lib/cn";

interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, error, hint, leftIcon, type = "text", id, className, ...props }, ref) => {
    const autoId = useId();
    const inputId = id ?? autoId;
    const [show, setShow] = useState(false);
    const isPassword = type === "password";
    const inputType = isPassword ? (show ? "text" : "password") : type;

    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={inputId} className="block text-sm font-medium text-gray-700">
            {label}
          </label>
        )}
        <div className="relative">
          {leftIcon && (
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
              {leftIcon}
            </span>
          )}
          <input
            id={inputId}
            ref={ref}
            type={inputType}
            aria-invalid={error ? true : undefined}
            aria-describedby={
              error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined
            }
            className={cn(
              "h-11 w-full rounded-xl border bg-white text-[15px] text-gray-900 outline-none",
              "transition-colors placeholder:text-gray-400 focus:ring-4",
              leftIcon ? "pl-10" : "pl-4",
              isPassword ? "pr-11" : "pr-4",
              error
                ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                : "border-gray-200 focus:border-brand-500 focus:ring-brand-500/15",
              className,
            )}
            {...props}
          />
          {isPassword && (
            <button
              type="button"
              tabIndex={-1}
              onClick={() => setShow((s) => !s)}
              aria-label={show ? "Hide password" : "Show password"}
              className="absolute right-3 top-1/2 -translate-y-1/2 p-0.5 text-gray-400 hover:text-gray-600"
            >
              {show ? (
                <EyeOff className="h-[18px] w-[18px]" />
              ) : (
                <Eye className="h-[18px] w-[18px]" />
              )}
            </button>
          )}
        </div>
        {error ? (
          <p id={`${inputId}-error`} className="text-sm text-red-500">
            {error}
          </p>
        ) : hint ? (
          <p id={`${inputId}-hint`} className="text-sm text-gray-400">
            {hint}
          </p>
        ) : null}
      </div>
    );
  },
);
TextField.displayName = "TextField";
