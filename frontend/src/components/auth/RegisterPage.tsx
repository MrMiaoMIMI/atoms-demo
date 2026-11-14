import type { FormEvent } from "react";
import { useState } from "react";
import { api, ApiError } from "../../api";
import { isValidEmail, passwordError } from "../../lib/auth";
import AuthShell, {
  AuthAlert,
  AuthField,
  PasswordInput,
  authInputClass,
  authPrimaryClass,
} from "./AuthShell";
import { Spinner } from "../Icons";

interface Props {
  email: string;
  redirect: string;
  onNavigate: (path: string) => void;
}

export default function RegisterPage({
  email,
  redirect,
  onNavigate,
}: Props) {
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [alreadyRegistered, setAlreadyRegistered] = useState(false);
  const [touched, setTouched] = useState(false);

  const emailOk = isValidEmail(email);
  const pwdError = password ? passwordError(password) : null;
  const formError = touched ? pwdError : null;
  const loginPath =
    `/login?email=${encodeURIComponent(email.trim())}` +
    (redirect && redirect !== "/dashboard"
      ? `&redirect=${encodeURIComponent(redirect)}`
      : "");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!emailOk) {
      setError("邮箱地址无效，请返回登录页重新输入。");
      return;
    }
    const invalid = passwordError(password);
    if (invalid || loading) return;

    setLoading(true);
    setError(null);
    try {
      const result = await api.register(
        email.trim(),
        password,
        redirect || "/dashboard"
      );
      try {
        window.sessionStorage.setItem("atoms.checkEmail.email", email.trim());
        window.sessionStorage.setItem(
          "atoms.devVerifyUrl",
          result.dev_verify_url ?? ""
        );
        window.sessionStorage.setItem(
          "atoms.checkEmail.warning",
          result.warning ?? ""
        );
        window.sessionStorage.setItem(
          "atoms.checkEmail.sent",
          result.verification_sent ? "1" : "0"
        );
        window.sessionStorage.setItem(
          "atoms.checkEmail.redirect",
          redirect || "/dashboard"
        );
      } catch {
        // Storage may be blocked; the check-email page still works.
      }
      onNavigate(`/register/verify?email=${encodeURIComponent(email.trim())}`);
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        setAlreadyRegistered(true);
      }
      setError(err instanceof Error ? err.message : "注册失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      onBack={() =>
        onNavigate(loginPath)
      }
      backLabel="返回"
    >
      <div className="text-center">
        <h1 className="text-[24px] font-semibold tracking-[-0.4px] text-ink-95">
          创建你的账户
        </h1>
        <p className="mt-2 text-[14px] text-ink-55">设置你的密码以继续</p>
      </div>

      <div className="mt-7 space-y-4">
        {error ? <AuthAlert>{error}</AuthAlert> : null}
        {!emailOk ? (
          <AuthAlert kind="info">
            没有读到有效的邮箱地址，请返回登录页重新输入。
          </AuthAlert>
        ) : null}

        <form onSubmit={submit} className="space-y-4">
          <AuthField label="邮箱">
            <input
              type="email"
              value={email}
              readOnly
              className={`${authInputClass} bg-[#F2F2F0] text-ink-55`}
            />
          </AuthField>

          <AuthField
            label="密码"
            hint="至少 8 位，需要同时包含字母和数字。"
          >
            <PasswordInput
              value={password}
              onChange={setPassword}
              autoComplete="new-password"
              autoFocus
            />
          </AuthField>

          {formError ? (
            <p className="text-[11px] text-danger">{formError}</p>
          ) : null}

          <button
            type="submit"
            disabled={!emailOk || Boolean(pwdError) || !password || loading}
            className={authPrimaryClass}
          >
            {loading ? <Spinner size={15} /> : "继续"}
          </button>
        </form>

        {alreadyRegistered ? (
          <button
            type="button"
            onClick={() =>
              onNavigate(loginPath)
            }
            className="w-full text-center text-[12px] text-brand-600 transition hover:underline"
          >
            该邮箱已注册，直接登录
          </button>
        ) : null}

        <button
          type="button"
          onClick={() =>
            onNavigate(loginPath)
          }
          className="w-full text-center text-[12px] text-ink-55 transition hover:text-ink-95"
        >
          返回登录
        </button>
      </div>
    </AuthShell>
  );
}
