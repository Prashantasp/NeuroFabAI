/** Formatting helpers shared across the UI so units and dates read consistently. */

const BYTE_UNITS = ["B", "KB", "MB", "GB", "TB"] as const;

export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const exponent = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    BYTE_UNITS.length - 1,
  );
  const value = bytes / 1024 ** exponent;
  // Bytes and KB are never fractional in a UI; larger units read better with one decimal.
  return `${value.toFixed(exponent < 2 ? 0 : 1)} ${BYTE_UNITS[exponent]}`;
}

export function formatNumber(value: number): string {
  return Number.isFinite(value) ? value.toLocaleString() : "0";
}

export function formatDuration(seconds: number | null | undefined): string {
  if (!seconds || seconds <= 0) return "—";
  if (seconds < 60) return `${seconds.toFixed(1)}s`;
  const minutes = Math.floor(seconds / 60);
  const remainder = Math.round(seconds % 60);
  return remainder ? `${minutes}m ${remainder}s` : `${minutes}m`;
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 31_536_000],
  ["month", 2_592_000],
  ["week", 604_800],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/**
 * "3 minutes ago", "in 2 days".
 *
 * Rendered client-side only. Formatting a relative time on the server produces
 * a hydration mismatch, because the two runs happen at different instants.
 */
export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const timestamp = new Date(iso).getTime();
  if (Number.isNaN(timestamp)) return "—";

  const deltaSeconds = (timestamp - Date.now()) / 1000;
  const absolute = Math.abs(deltaSeconds);
  if (absolute < 45) return "just now";

  const formatter = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, seconds] of RELATIVE_UNITS) {
    if (absolute >= seconds) {
      return formatter.format(Math.round(deltaSeconds / seconds), unit);
    }
  }
  return formatter.format(Math.round(deltaSeconds), "second");
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** Initials for an avatar, from a name or email. */
export function initialsOf(value: string | null | undefined): string {
  if (!value) return "?";
  return (
    value
      .split(/[\s@._-]+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase() ?? "")
      .join("") || "?"
  );
}
