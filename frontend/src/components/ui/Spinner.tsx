/**
 * AGRIOS — Spinner Component
 * Used in loading states across all screens.
 */

interface SpinnerProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

const sizeClasses = {
  sm: "w-4 h-4 border-2",
  md: "w-6 h-6 border-2",
  lg: "w-10 h-10 border-3",
};

export function Spinner({ size = "md", className = "" }: SpinnerProps) {
  return (
    <div
      className={`
        ${sizeClasses[size]}
        rounded-full
        border-brand-200
        border-t-brand-600
        animate-spin
        ${className}
      `}
      role="status"
      aria-label="Loading"
    />
  );
}
