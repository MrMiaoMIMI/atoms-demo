export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function isValidEmail(value: string): boolean {
  const email = value.trim();
  if (!email || email.length > 254) return false;
  if (!EMAIL_RE.test(email) || email.includes("..")) return false;
  const [local, domain] = email.split("@");
  if (!local || !domain) return false;
  if (domain.startsWith(".") || domain.endsWith(".")) return false;
  return domain.includes(".");
}

export function passwordError(value: string): string | null {
  if (value.length < 8) return "密码至少需要 8 个字符";
  if (value.length > 64) return "密码长度不能超过 64 个字符";
  if (!/[A-Za-z]/.test(value)) return "密码需要包含字母";
  if (!/\d/.test(value)) return "密码需要包含数字";
  return null;
}

/** Only allow same-site paths; never navigate to an external URL. */
export function safeRedirect(
  value: string | null,
  fallback = "/dashboard"
): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) {
    return fallback;
  }
  if (value.includes("\\") || value.includes("\n") || value.includes("\r")) {
    return fallback;
  }
  if (
    value.startsWith("/login") ||
    value.startsWith("/register") ||
    value.startsWith("/verify-email") ||
    value.startsWith("/password/")
  ) {
    return fallback;
  }
  return value;
}

export function readQuery(name: string): string | null {
  try {
    return new URLSearchParams(window.location.search).get(name);
  } catch {
    return null;
  }
}
