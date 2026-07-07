import { forwardRef, useId } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: string;
}

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
  label?: string;
  error?: string;
  hint?: string;
  options: SelectOption[];
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, error, hint, options, id, className, ...props }, ref) => {
    const autoId = useId();
    const sid = id ?? autoId;
    return (
      <div className="space-y-1.5">
        {label && (
          <label htmlFor={sid} className="block text-sm font-medium text-gray-700">
            {label}
          </label>
        )}
        <div className="relative">
          <select
            id={sid}
            ref={ref}
            className={cn(
              "h-11 w-full appearance-none rounded-xl border bg-white pl-4 pr-10 text-[15px] text-gray-900",
              "outline-none transition-colors focus:ring-4",
              error
                ? "border-red-400 focus:border-red-500 focus:ring-red-500/15"
                : "border-gray-200 focus:border-brand-500 focus:ring-brand-500/15",
              className,
            )}
            {...props}
          >
            {options.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
          <ChevronDown className="pointer-events-none absolute right-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
        </div>
        {error ? (
          <p className="text-sm text-red-500">{error}</p>
        ) : hint ? (
          <p className="text-sm text-gray-400">{hint}</p>
        ) : null}
      </div>
    );
  },
);
Select.displayName = "Select";
