import type { FormEvent } from "react";
import { useState } from "react";
import { api } from "../../api";
import { passwordError } from "../../lib/auth";
import { CheckCircle, Spinner } from "../Icons";
import AuthShell, {
  AuthAlert,
  AuthField,
  PasswordInput,
  authPrimaryClass,
} from "./AuthShell";

interface Props {
  token: string;
  email: string;
  onNavigate: (path: string) => void;
}

export default function ResetPasswordPage({
  token,
  email,
  onNavigate,
}: Props) {
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [touched, setTouched] = useState(false);

  const pwdError = password ? passwordError(password) : null;
  const mismatch = confirm.length > 0 && confirm !== password;
  const canSubmit =
    Boolean(token) &&
    !pwdError &&
    password.length > 0 &&
    confirm === password &&
    !loading;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setTouched(true);
    if (!canSubmit) return;
    setLoading(true);
    setError(null);
    try {
      await api.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "重置失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthShell
      onBack={() =>
        onNavigate(`/login?email=${encodeURIComponent(email.trim())}`)
      }
      backLabel="返回登录"
    >
      <div className="text-center">
        {done ? (
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-[#EFF9F3] text-[#1E7A45]">
            <CheckCircle size={23} />
          </div>
        ) : null}
        <h1 className="mt-5 text-[24px] font-semibold tracking-[-0.4px] text-ink-95">
          {done ? "密码已重置" : "设置新密码"}
        </h1>
        <p className="mt-2 text-[14px] leading-6 text-ink-55">
          {done ? (
            "请使用新密码重新登录。"
          ) : (
            <>
              请选择一个强密码用于
              <br />
              <span className="font-medium text-ink-95">{email || "你的账号"}</span>
            </>
          )}
        </p>
      </div>

      <div className="mt-7 space-y-3">
        {error ? <AuthAlert>{error}</AuthAlert> : null}
        {!token ? (
          <AuthAlert>重置链接缺少 token，请重新发起忘记密码流程。</AuthAlert>
        ) : null}

        {done ? (
          <button
            type="button"
            onClick={() =>
              onNavigate(
                `/login?reset=1${email ? `&email=${encodeURIComponent(email)}` : ""}`
              )
            }
            className={authPrimaryClass}
          >
            返回登录
          </button>
        ) : (
          <form onSubmit={submit} className="space-y-4">
            <AuthField
              label="新密码"
              hint="至少 8 位，需要同时包含字母和数字。"
            >
              <PasswordInput
                value={password}
                onChange={setPassword}
                placeholder="输入新密码"
                autoComplete="new-password"
                autoFocus
              />
            </AuthField>
            <AuthField label="确认新密码">
              <PasswordInput
                value={confirm}
                onChange={setConfirm}
                placeholder="再次输入新密码"
                autoComplete="new-password"
              />
            </AuthField>

            {touched && pwdError ? (
              <p className="text-[11px] text-danger">{pwdError}</p>
            ) : null}
            {mismatch ? (
              <p className="text-[11px] text-danger">两次输入的密码不一致</p>
            ) : null}

            <button
              type="submit"
              disabled={!canSubmit}
              className={authPrimaryClass}
            >
              {loading ? <Spinner size={15} /> : "重置密码"}
            </button>
          </form>
        )}

        {!done ? (
          <button
            type="button"
            onClick={() =>
              onNavigate(`/login?email=${encodeURIComponent(email.trim())}`)
            }
            className="w-full text-center text-[12px] text-ink-55 transition hover:text-ink-95"
          >
            返回
          </button>
        ) : null}
      </div>
    </AuthShell>
  );
}
