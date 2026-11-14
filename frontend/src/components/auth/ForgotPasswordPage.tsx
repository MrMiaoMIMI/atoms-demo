import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { api } from "../../api";
import { isValidEmail } from "../../lib/auth";
import { copyText } from "../../lib/clipboard";
import { Copy, Mail, Spinner } from "../Icons";
import AuthShell, {
  AuthAlert,
  authInputClass,
  authPrimaryClass,
} from "./AuthShell";

interface Props {
  initialEmail?: string;
  onNavigate: (path: string) => void;
}

export default function ForgotPasswordPage({
  initialEmail = "",
  onNavigate,
}: Props) {
  const [email, setEmail] = useState(initialEmail);
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [delivered, setDelivered] = useState<boolean | null>(null);
  const [mailMode, setMailMode] = useState<"smtp" | "dev" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);
  const [copied, setCopied] = useState(false);

  const emailValid = isValidEmail(email);
  const showEmailError = touched && email.length > 0 && !emailValid;

  useEffect(() => {
    let cancelled = false;
    api
      .providers()
      .then((data) => {
        if (!cancelled) setMailMode(data.mail);
      })
      .catch(() => {
        // Keep the neutral dev-link copy if the providers call fails.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!emailValid || loading) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.forgotPassword(email.trim());
      setSent(true);
      setDevLink(result.dev_reset_url ?? null);
      setDelivered(result.delivered ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "发送失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  async function copyLink() {
    if (!devLink) return;
    if (await copyText(devLink)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
  }

  const delivery =
    mailMode === null
      ? { badge: "开发链接", text: "可直接使用下方链接" }
      : mailMode === "dev"
        ? { badge: "演示模式", text: "当前未配置 SMTP，可直接使用下方链接" }
        : delivered === false
          ? { badge: "发送失败", text: "邮件发送失败，可直接使用下方链接" }
          : delivered === true
            ? { badge: "邮件已发送", text: "邮件已发送，也可直接使用下方链接" }
            : { badge: "开发链接", text: "可直接使用下方链接" };

  return (
    <AuthShell
      onBack={() =>
        onNavigate(`/login?email=${encodeURIComponent(email.trim())}`)
      }
      backLabel="返回登录"
    >
      <div className="text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand">
          <Mail size={22} />
        </div>
        <h1 className="mt-5 text-[24px] font-semibold tracking-[-0.4px] text-ink-95">
          忘记密码
        </h1>
        <p className="mt-2 text-[14px] leading-6 text-ink-55">
          我们将向你发送一个重置密码的链接
        </p>
      </div>

      <div className="mt-7 space-y-3">
        {error ? <AuthAlert>{error}</AuthAlert> : null}

        {sent ? (
          <>
            <AuthAlert kind="success">
              如果该邮箱已注册，你将收到重置密码的链接。
            </AuthAlert>
            {devLink ? (
              <div className="rounded-xl border border-brand-200 bg-brand-50 p-4">
                <div className="flex items-center gap-2 text-[12px] font-medium text-brand-600">
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px]">
                    {delivery.badge}
                  </span>
                  {delivery.text}
                </div>
                <a
                  href={devLink}
                  className={`${authPrimaryClass} mt-3`}
                  style={{ background: "#4267FF" }}
                >
                  重置密码
                </a>
                <div className="mt-2 flex items-center gap-2">
                  <p className="min-w-0 flex-1 break-all text-[10px] leading-4 text-brand-600/70">
                    {devLink}
                  </p>
                  <button
                    type="button"
                    onClick={() => void copyLink()}
                    className="flex flex-none items-center gap-1 rounded-md border border-brand-200 bg-white px-2 py-1 text-[11px] text-brand-600"
                  >
                    <Copy size={12} />
                    {copied ? "已复制" : "复制"}
                  </button>
                </div>
              </div>
            ) : null}
            <button
              type="button"
              onClick={() =>
                onNavigate(`/login?email=${encodeURIComponent(email.trim())}`)
              }
              className={authPrimaryClass}
            >
              返回登录
            </button>
          </>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <input
              type="email"
              name="email"
              value={email}
              autoFocus
              autoComplete="email"
              placeholder="输入你的邮箱"
              onChange={(event) => setEmail(event.target.value)}
              onBlur={() => setTouched(true)}
              className={authInputClass}
            />
            {showEmailError ? (
              <p className="text-[11px] text-danger">请输入有效的邮箱地址</p>
            ) : null}
            <button
              type="submit"
              disabled={!emailValid || loading}
              className={authPrimaryClass}
            >
              {loading ? <Spinner size={15} /> : "继续"}
            </button>
          </form>
        )}

        {!sent ? (
          <button
            type="button"
            onClick={() =>
              onNavigate(`/login?email=${encodeURIComponent(email.trim())}`)
            }
            className="w-full text-center text-[12px] text-ink-55 transition hover:text-ink-95"
          >
            返回登录
          </button>
        ) : null}
      </div>
    </AuthShell>
  );
}
