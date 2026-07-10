import { Logo } from "@/components/ui/Logo";

/** Full-screen status page (unauthorized, session expired, offline, error). */
export function StatusScreen({
  icon,
  title,
  description,
  action,
}: {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex min-h-[100dvh] flex-col items-center justify-center bg-[#f6f8f6] px-6 text-center dark:bg-[#0b0e12]">
      <Logo variant="lockup" className="mb-10 h-8 w-auto dark:hidden" />
      <Logo variant="lockup" tone="white" className="mb-10 hidden h-8 w-auto dark:block" />
      {icon && (
        <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-brand-600 shadow-sm dark:bg-white/[0.04] dark:text-brand-300">
          {icon}
        </div>
      )}
      <h1 className="text-xl font-semibold tracking-[-0.01em] text-gray-900 dark:text-white">
        {title}
      </h1>
      {description && (
        <p className="mt-2 max-w-sm text-[15px] text-gray-500 dark:text-gray-400">{description}</p>
      )}
      {action && <div className="mt-7">{action}</div>}
    </div>
  );
}
