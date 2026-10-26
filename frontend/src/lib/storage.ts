/**
 * Remembered UI preferences (sidebar open, suggestions minimised…).
 * Storage can be unavailable (private mode, blocked site data), so every
 * access is guarded and falls back to the default.
 */
export function readFlag(key: string, fallback: boolean): boolean {
  try {
    const value = localStorage.getItem(key)
    return value === null ? fallback : value === '1'
  } catch {
    return fallback
  }
}

export function writeFlag(key: string, value: boolean): void {
  try {
    localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // preference just isn't remembered this time
  }
}
