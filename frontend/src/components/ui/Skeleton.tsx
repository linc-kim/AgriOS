import { cn } from "@/lib/cn";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      aria-hidden
      className={cn(
        "animate-pulse rounded-md bg-gray-200/70 dark:bg-white/10",
        className,
      )}
    />
  );
}
