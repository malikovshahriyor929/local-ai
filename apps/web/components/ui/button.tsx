import { ButtonHTMLAttributes, forwardRef } from "react";
import { cn } from "@/lib/utils";
export const Button = forwardRef<HTMLButtonElement, ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "secondary" | "ghost" }>(({ className, variant = "default", ...props }, ref) => <button ref={ref} className={cn("inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-40", variant === "default" && "bg-indigo-500 text-white hover:bg-indigo-400", variant === "secondary" && "border border-border bg-card text-slate-100 hover:bg-slate-800", variant === "ghost" && "text-slate-300 hover:bg-slate-800", className)} {...props} />);
Button.displayName = "Button";
