import { useEffect, useRef, useState } from "react";
import { api } from "../../api";
import type { AuthUser } from "../../types";
import { AlertTriangle, AtomsMark, CheckCircle, Spinner } from "../Icons";
import AuthShell, { authPrimaryClass, authSecondaryClass } from "./AuthShell";

interface Props {
  token: string;
  email: string;
  redirect: string;
  onAuthenticated: (user: AuthUser, redirect: string) => void;
  onNavigate: (path: string) => void;
}

type Status = "loading" | "success" | "error";

export default function VerifyEmailPage({
  token,
  email,
  redirect,
  onAuthenticated,
  onNavigate,
}: Props) {
  // React StrictMode runs effects twice in development. Keep one shared
  // promise per token so the one-time token is consumed exactly once, while
  // each effect attachment still delivers the result to the live component.
  const promiseRef = useRef<ReturnType<typeof api.verifyEmail> | null>(null);
  const tokenRef = useRef<string | null>(null);
  const [status, setStatus] = useState<Status>("loading");
  const [message, setMessage] = useState("");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [target, setTarget] = useState(redirect || "/dashboard");
  const loginParams = new URLSearchParams();
  if (email) loginParams.set("email", email);
  if (redirect && redirect !== "/dashboard") loginParams.set("redirect", redirect);
  const loginPath = `/login${
    loginParams.toString() ? `?${loginParams.toString()}` : ""
  }`;

  useEffect(() => {
    if (!token) {
      setStatus("error");
      setMessage("验证链接缺少 token，请返回注册页面重新发送。");
      return;
    }
    if (tokenRef.current !== token) {
      tokenRef.current = token;
      promiseRef.current = null;
    }
    if (!promiseRef.current) promiseRef.current = api.verifyEmail(token);
    let active = true;
    promiseRef.current
      .then((result) => {
        if (!active) return;
        try {
          window.sessionStorage.removeItem("atoms.devVerifyUrl");
          window.sessionStorage.removeItem("atoms.checkEmail.warning");
        } catch {
          // Storage may be blocked.
        }
        setUser(result.user);
        // The email URL carries the redirect the user originally wanted;
        // prefer it over the API's generic dashboard fallback.
        setTarget(redirect || result.redirect || "/dashboard");
        setStatus("success");
      })
      .catch((err: unknown) => {
        if (!active) return;
        setStatus("error");
        setMessage(
          err instanceof Error ? err.message : "验证失败，请稍后重试。"
        );
      });
    return () => {
      active = false;
    };
  }, [token, redirect]);

  useEffect(() => {
    if (status !== "success" || !user) return;
    const timer = window.setTimeout(
      () => onAuthenticated(user, target),
      1400
    );
    return () => window.clearTimeout(timer);
  }, [status, user, target, onAuthenticated]);

  return (
    <AuthShell
      onBack={() =>
        onNavigate(loginPath)
      }
      backLabel="返回登录"
    >
      <div className="text-center">
        <div
          className={`mx-auto grid h-12 w-12 place-items-center rounded-2xl ${
            status === "success"
              ? "bg-[#EFF9F3] text-[#1E7A45]"
              : status === "error"
                ? "bg-[#FFF5F4] text-[#B42318]"
                : "bg-brand-50 text-brand"
          }`}
        >
          {status === "success" ? (
            <CheckCircle size={23} />
          ) : status === "error" ? (
            <AlertTriangle size={23} />
          ) : (
            <AtomsMark size={22} />
          )}
        </div>

        <h1 className="mt-5 text-[24px] font-semibold tracking-[-0.4px] text-ink-95">
          {status === "success"
            ? "邮箱验证成功"
            : status === "error"
              ? "验证失败"
              : "正在验证邮箱"}
        </h1>
        <p className="mt-2 text-[14px] leading-6 text-ink-55">
          {status === "success"
            ? "你的邮箱已验证，正在进入工作台…"
            : status === "error"
              ? message
              : "请稍候，我们正在验证你的电子邮件地址。"}
        </p>
      </div>

      <div className="mt-7 space-y-3">
        {status === "loading" ? (
          <div className="flex items-center justify-center gap-2 py-2 text-[12px] text-ink-30">
            <Spinner size={16} className="text-brand" />
            正在验证
          </div>
        ) : null}

        {status === "success" && user ? (
          <button
            type="button"
            onClick={() => onAuthenticated(user, target)}
            className={authPrimaryClass}
          >
            进入工作台
          </button>
        ) : null}

        {status === "error" ? (
          <>
            {email ? (
              <button
                type="button"
                onClick={() =>
                  onNavigate(
                    `/register/verify?email=${encodeURIComponent(email)}`
                  )
                }
                className={authSecondaryClass}
              >
                返回注册页面重新发送
              </button>
            ) : null}
            <button
              type="button"
              onClick={() =>
                onNavigate(loginPath)
              }
              className={authPrimaryClass}
            >
              返回登录
            </button>
          </>
        ) : null}
      </div>
    </AuthShell>
  );
}
