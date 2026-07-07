import { forwardRef } from "react";
import { Loader2 } from "lucide-react";
import { cn } from "@/lib/cn";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  fullWidth?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

const VARIANTS: Record<Variant, string> = {
  primary:
    "bg-brand-600 text-white shadow-sm hover:bg-brand-700 active:bg-brand-800 " +
    "focus-visible:ring-brand-600/40",
  secondary:
    "bg-white text-gray-800 border border-gray-200 hover:bg-gray-50 " +
    "active:bg-gray-100 focus-visible:ring-gray-300",
  ghost:
    "bg-transparent text-gray-600 hover:bg-gray-100 active:bg-gray-200 " +
    "focus-visible:ring-gray-300",
  danger:
    "bg-red-600 text-white shadow-sm hover:bg-red-700 active:bg-red-800 " +
    "focus-visible:ring-red-500/40",
};

const SIZES: Record<Size, string> = {
  sm: "h-9 px-3.5 text-sm rounded-lg gap-1.5",
  md: "h-11 px-5 text-sm rounded-xl gap-2",
  lg: "h-12 px-6 text-base rounded-xl gap-2",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      fullWidth = false,
      leftIcon,
      rightIcon,
      className,
      children,
      disabled,
      ...props
    },
    ref,
  ) => (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center font-semibold tracking-[-0.01em]",
        "transition-all duration-150 ease-[cubic-bezier(.16,1,.3,1)]",
        "outline-none focus-visible:ring-4 active:translate-y-px",
        "disabled:opacity-55 disabled:pointer-events-none",
        VARIANTS[variant],
        SIZES[size],
        fullWidth && "w-full",
        className,
      )}
      {...props}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
      ) : (
        leftIcon
      )}
      {children}
      {!loading && rightIcon}
    </button>
  ),
);
Button.displayName = "Button";
