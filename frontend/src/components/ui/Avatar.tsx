import { cn } from "@/lib/cn";

function initials(name?: string | null, email?: string | null): string {
  const src = (name && name.trim()) || email?.split("@")[0] || "";
  const parts = src.split(/[\s._-]+/).filter(Boolean);
  const two = (parts[0]?.[0] ?? "G") + (parts[1]?.[0] ?? "");
  return two.toUpperCase();
}

export function Avatar({
  name,
  email,
  className,
}: {
  name?: string | null;
  email?: string | null;
  className?: string;
}) {
  return (
    <span
      aria-hidden
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full bg-brand-600 text-[13px] font-semibold text-white",
        className,
      )}
    >
      {initials(name, email)}
    </span>
  );
}
