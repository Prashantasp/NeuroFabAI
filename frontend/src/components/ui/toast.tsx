"use client";

/**
 * Toast notifications.
 *
 * Replaces the `alert()` / `confirm()` calls and inline red banners the previous
 * UI used. Toasts are announced to screen readers via a polite live region and
 * auto-dismiss, except errors, which stay until dismissed so a failure is never
 * missed.
 */

import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

type ToastVariant = "success" | "error" | "warning" | "info" | "loading";

interface Toast {
  id: string;
  title: string;
  description?: string;
  variant: ToastVariant;
  action?: { label: string; onClick: () => void };
}

interface ToastOptions {
  description?: string;
  /** Milliseconds before auto-dismiss. `0` keeps it until dismissed. */
  duration?: number;
  action?: { label: string; onClick: () => void };
}

interface ToastContextValue {
  toast: (variant: ToastVariant, title: string, options?: ToastOptions) => string;
  success: (title: string, options?: ToastOptions) => string;
  error: (title: string, options?: ToastOptions) => string;
  warning: (title: string, options?: ToastOptions) => string;
  info: (title: string, options?: ToastOptions) => string;
  loading: (title: string, options?: ToastOptions) => string;
  dismiss: (id: string) => void;
  update: (id: string, variant: ToastVariant, title: string, options?: ToastOptions) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const DEFAULT_DURATIONS: Record<ToastVariant, number> = {
  success: 4000,
  info: 4000,
  warning: 6000,
  // Errors and in-flight operations persist: an auto-hiding failure message is
  // one the user can miss entirely.
  error: 0,
  loading: 0,
};

const VARIANT_STYLES: Record<ToastVariant, { icon: ReactNode; accent: string }> = {
  success: { icon: <CheckCircle2 className="size-4" />, accent: "text-ok" },
  error: { icon: <XCircle className="size-4" />, accent: "text-danger" },
  warning: { icon: <AlertTriangle className="size-4" />, accent: "text-warn" },
  info: { icon: <Info className="size-4" />, accent: "text-info" },
  loading: { icon: <Loader2 className="size-4 animate-spin" />, accent: "text-muted-foreground" },
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef(new Map<string, ReturnType<typeof setTimeout>>());

  const dismiss = useCallback((id: string) => {
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const schedule = useCallback(
    (id: string, variant: ToastVariant, duration?: number) => {
      const existing = timers.current.get(id);
      if (existing) clearTimeout(existing);

      const ms = duration ?? DEFAULT_DURATIONS[variant];
      if (ms > 0) timers.current.set(id, setTimeout(() => dismiss(id), ms));
    },
    [dismiss],
  );

  const toast = useCallback(
    (variant: ToastVariant, title: string, options?: ToastOptions) => {
      const id = Math.random().toString(36).slice(2);
      setToasts((current) => [
        // Cap the stack; older toasts are the least relevant.
        ...current.slice(-3),
        { id, title, description: options?.description, variant, action: options?.action },
      ]);
      schedule(id, variant, options?.duration);
      return id;
    },
    [schedule],
  );

  const update = useCallback(
    (id: string, variant: ToastVariant, title: string, options?: ToastOptions) => {
      setToasts((current) =>
        current.map((t) =>
          t.id === id
            ? { ...t, variant, title, description: options?.description, action: options?.action }
            : t,
        ),
      );
      schedule(id, variant, options?.duration);
    },
    [schedule],
  );

  // Clear every pending timer when the provider unmounts.
  useEffect(() => {
    const pending = timers.current;
    return () => {
      pending.forEach(clearTimeout);
      pending.clear();
    };
  }, []);

  const value = useMemo<ToastContextValue>(
    () => ({
      toast,
      dismiss,
      update,
      success: (title, options) => toast("success", title, options),
      error: (title, options) => toast("error", title, options),
      warning: (title, options) => toast("warning", title, options),
      info: (title, options) => toast("info", title, options),
      loading: (title, options) => toast("loading", title, options),
    }),
    [toast, dismiss, update],
  );

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div
        role="region"
        aria-label="Notifications"
        className="pointer-events-none fixed inset-x-0 bottom-0 z-[100] flex flex-col items-center gap-2 p-4 sm:inset-x-auto sm:right-0 sm:top-0 sm:items-end sm:p-6"
      >
        {toasts.map((item) => (
          <ToastCard key={item.id} toast={item} onDismiss={() => dismiss(item.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const { icon, accent } = VARIANT_STYLES[toast.variant];

  return (
    <div
      // Errors interrupt; everything else waits for a pause in speech.
      role={toast.variant === "error" ? "alert" : "status"}
      aria-live={toast.variant === "error" ? "assertive" : "polite"}
      className={cn(
        "pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-lg border bg-popover p-3.5 text-popover-foreground shadow-md",
        "animate-in fade-in-0 slide-in-from-bottom-2 sm:slide-in-from-right-2",
      )}
    >
      <span className={cn("mt-0.5 shrink-0", accent)} aria-hidden>
        {icon}
      </span>

      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-snug">{toast.title}</p>
        {toast.description && (
          <p className="mt-1 text-sm leading-snug text-muted-foreground break-words">
            {toast.description}
          </p>
        )}
        {toast.action && (
          <button
            type="button"
            onClick={() => {
              toast.action?.onClick();
              onDismiss();
            }}
            className="mt-2 text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            {toast.action.label}
          </button>
        )}
      </div>

      {toast.variant !== "loading" && (
        <button
          type="button"
          onClick={onDismiss}
          aria-label="Dismiss notification"
          className="-m-1 shrink-0 rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          <X className="size-4" />
        </button>
      )}
    </div>
  );
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used within a ToastProvider");
  return context;
}
