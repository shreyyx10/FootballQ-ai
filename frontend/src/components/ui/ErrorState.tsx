import { cn } from "@/lib/utils";

export function ErrorState({
  message,
  className,
}: {
  message: string;
  className?: string;
}) {
  return (
    <div
      role="alert"
      className={cn(
        "flex items-start gap-3 rounded-xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger",
        className
      )}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        className="mt-0.5 h-5 w-5 flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        strokeWidth={1.8}
        aria-hidden="true"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M12 9v3.75m9-1.5a9 9 0 1 1-18 0 9 9 0 0 1 18 0zm-9 3.75h.008v.008H12v-.008z"
        />
      </svg>
      <span>{message}</span>
    </div>
  );
}
