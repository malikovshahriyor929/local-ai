import { cn } from "@/lib/utils";
export function Badge({ className, children }: React.PropsWithChildren<{ className?: string }>) { return <span className={cn("inline-flex items-center rounded-full border border-border bg-muted px-2.5 py-1 text-xs font-medium text-slate-200", className)}>{children}</span>; }
