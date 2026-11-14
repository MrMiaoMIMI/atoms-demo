import { useEffect, useState } from "react";
import { api } from "../../api";
import { copyText } from "../../lib/clipboard";
import { Copy, Mail, Spinner } from "../Icons";
import AuthShell, {
  AuthAlert,
  authPrimaryClass,
  authSecondaryClass,
} from "./AuthShell";

interface Props {
  email: string;
  onNavigate: (path: string) => void;
}

function readStored(key: string): string | null {
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

export default function CheckEmailPage({ email, onNavigate }: Props) {
  const [devLink, setDevLink] = useState<string | null>(() => {
    const stored = readStored("atoms.devVerifyUrl");
    const storedEmail = readStored("atoms.checkEmail.email");
    return storedEmail === email && stored ? stored : null;
  });
  const [warning] = useState<string | null>(() => {
    const storedEmail = readStored("atoms.checkEmail.email");
    return storedEmail === email
      ? readStored("atoms.checkEmail.warning")
      : null;
  });
  const [sent, setSent] = useState<boolean | null>(() => {
    const storedEmail = readStored("atoms.checkEmail.email");
    if (storedEmail !== email) return null;
    const value = readStored("atoms.checkEmail.sent");
    return value === "1" ? true : value === "0" ? false : null;
  });
  const [mailMode, setMailMode] = useState<"smtp" | "dev" | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [countdown, setCountdown] = useState(0);
  const [copied, setCopied] = useState(false);
  const storedRedirect = readStored("atoms.checkEmail.redirect") || "/dashboard";
  const loginPath =
    `/login?email=${encodeURIComponent(email.trim())}` +
    (storedRedirect !== "/dashboard"
      ? `&redirect=${encodeURIComponent(storedRedirect)}`
      : "");

  useEffect(() => {
    if (countdown <= 0) return;
    const timer = window.setInterval(
      () => setCountdown((value) => Math.max(0, value - 1)),
      1000
    );
    return () => window.clearInterval(timer);
  }, [countdown]);

  useEffect(() => {
    let cancelled = false;
    api
      .providers()
      .then((data) => {
        if (!cancelled) setMailMode(data.mail);
      })
      .catch(() => {
        // Keep the neutral "开发链接" copy if the providers call fails.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function resend() {
    if (loading || countdown > 0 || !email) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const result = await api.resendVerification(email, storedRedirect);
      if (result.dev_verify_url) {
        setDevLink(result.dev_verify_url);
        try {
          window.sessionStorage.setItem(
            "atoms.devVerifyUrl",
            result.dev_verify_url
          );
        } catch {
          // Storage may be blocked.
        }
        setInfo("验证邮件已重新发送，开发模式链接已更新。");
      } else {
        setInfo("验证邮件已重新发送，请查收邮箱。");
      }
      setSent(result.sent);
      try {
        window.sessionStorage.setItem(
          "atoms.checkEmail.sent",
          result.sent ? "1" : "0"
        );
      } catch {
        // Storage may be blocked.
      }
      setCountdown(60);
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
      ? { badge: "开发链接", text: "可直接使用下方链接完成验证" }
      : mailMode === "dev"
        ? { badge: "演示模式", text: "当前未配置 SMTP，不会真的发送邮件" }
        : sent === false
          ? {
              badge: "发送失败",
              text: "验证邮件发送失败，可直接使用下方链接完成验证",
            }
          : sent === true
            ? {
                badge: "邮件已发送",
                text: "验证邮件已发送，也可直接使用下方链接完成验证",
              }
            : { badge: "开发链接", text: "可直接使用下方链接完成验证" };

  return (
    <AuthShell
      onBack={() =>
        onNavigate(loginPath)
      }
      backLabel="返回登录"
    >
      <div className="text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-brand-50 text-brand">
          <Mail size={22} />
        </div>
        <h1 className="mt-5 text-[24px] font-semibold tracking-[-0.4px] text-ink-95">
          查收你的邮件
        </h1>
        <p className="mt-2 text-[14px] leading-6 text-ink-55">
          我们已向{" "}
          <span className="font-medium text-ink-95">{email || "你的邮箱"}</span>
          <br />
          发送了一封验证邮件。点击邮件中的按钮即可激活账号。
        </p>
      </div>

      <div className="mt-6 space-y-3">
        {error ? <AuthAlert>{error}</AuthAlert> : null}
        {info ? <AuthAlert kind="success">{info}</AuthAlert> : null}
        {warning && !devLink ? <AuthAlert>{warning}</AuthAlert> : null}
        {!email ? (
          <AuthAlert>没有读到邮箱地址，请返回注册页面重新输入。</AuthAlert>
        ) : null}

        {devLink ? (
          <div className="rounded-xl border border-brand-200 bg-brand-50 p-4">
            <div className="flex items-center gap-2 text-[12px] font-medium text-brand-600">
              <span className="rounded-full bg-white px-2 py-0.5 text-[10px]">
                {delivery.badge}
              </span>
              {delivery.text}
            </div>
            <p className="mt-2 text-[12px] leading-5 text-brand-600/80">
              可以直接点击下面按钮完成验证，或复制链接到其它浏览器打开。
            </p>
            <a
              href={devLink}
              className={`${authPrimaryClass} mt-3`}
              style={{ background: "#4267FF" }}
            >
              验证邮箱
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
          onClick={resend}
          disabled={loading || countdown > 0 || !email}
          className={authSecondaryClass}
        >
          {loading ? <Spinner size={15} /> : null}
          {countdown > 0 ? `重新发送（${countdown}s）` : "重新发送验证邮件"}
        </button>

        <button
          type="button"
          onClick={() =>
            onNavigate(loginPath)
          }
          className="w-full text-center text-[12px] text-ink-55 transition hover:text-ink-95"
        >
          返回登录
        </button>

        <p className="text-center text-[11px] leading-5 text-ink-30">
          没收到邮件？请检查垃圾箱，或确认邮箱地址是否正确。
        </p>
      </div>
    </AuthShell>
  );
}
