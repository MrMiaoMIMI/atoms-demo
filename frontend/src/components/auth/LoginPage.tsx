import type { FormEvent } from 'react';
import { useEffect, useState } from 'react';
import { api, ApiError } from '../../api';
import { isValidEmail, safeRedirect } from '../../lib/auth';
import { copyText } from '../../lib/clipboard';
import type { AuthProviders, AuthUser } from '../../types';
import { Copy, Sparkle, Spinner } from '../Icons';
import AuthShell, {
  AuthAlert,
  AuthDivider,
  AuthField,
  AuthLegalNote,
  GoogleButton,
  PasswordInput,
  authInputClass,
  authPrimaryClass,
  authSecondaryClass,
} from './AuthShell';

interface Props {
  onNavigate: (path: string) => void;
  onAuthenticated: (user: AuthUser, redirect: string) => void;
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试';
}

export default function LoginPage({ onNavigate, onAuthenticated }: Props) {
  const params = new URLSearchParams(window.location.search);
  const redirect = safeRedirect(params.get('redirect'));
  const errorParam = params.get('error');
  const resetNotice = params.get('reset') === '1';

  const [providers, setProviders] = useState<AuthProviders | null>(null);
  const [step, setStep] = useState<'email' | 'password'>('email');
  const [email, setEmail] = useState(params.get('email') ?? '');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [quickLoading, setQuickLoading] = useState(false);
  const [resending, setResending] = useState(false);
  const [unverified, setUnverified] = useState(false);
  const [error, setError] = useState<string | null>(
    errorParam === 'google_failed'
      ? 'Google 登录失败，请重试或使用邮箱登录。'
      : errorParam === 'google_not_configured'
        ? 'Google 登录尚未配置，请使用邮箱登录。'
        : null,
  );
  const [info, setInfo] = useState<string | null>(
    resetNotice ? '密码已重置，请使用新密码登录。' : null,
  );
  const [emailTouched, setEmailTouched] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [created, setCreated] = useState<{
    user: AuthUser;
    password: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  const emailValid = isValidEmail(email);
  const showEmailError = emailTouched && email.length > 0 && !emailValid;
  const quickPassword = providers?.quick_password || 'AtomsDemo2026';

  useEffect(() => {
    let cancelled = false;
    api
      .providers()
      .then((data) => {
        if (!cancelled) setProviders(data);
      })
      .catch(() => {
        if (!cancelled) setProviders(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function submitEmail(event: FormEvent) {
    event.preventDefault();
    setEmailTouched(true);
    if (!emailValid || loading) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    try {
      const result = await api.checkEmail(email.trim());
      if (result.registered) {
        setStep('password');
        setPassword('');
        setUnverified(false);
      } else {
        onNavigate(
          `/register?email=${encodeURIComponent(email.trim())}` +
            (redirect !== '/dashboard'
              ? `&redirect=${encodeURIComponent(redirect)}`
              : ''),
        );
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setLoading(false);
    }
  }

  async function submitPassword(event: FormEvent) {
    event.preventDefault();
    if (!password || loading) return;
    setLoading(true);
    setError(null);
    setInfo(null);
    setUnverified(false);
    try {
      const user = await api.login(email.trim(), password);
      onAuthenticated(user, redirect);
    } catch (err) {
      setError(errorMessage(err));
      if (err instanceof ApiError && err.status === 403) setUnverified(true);
    } finally {
      setLoading(false);
    }
  }

  async function quickLogin() {
    setEmailTouched(true);
    if (!emailValid || quickLoading) return;
    setQuickLoading(true);
    setError(null);
    setInfo(null);
    try {
      const result = await api.quickLogin(email.trim());
      if (result.created) {
        setCreated({
          user: result.user,
          password: result.default_password || quickPassword,
        });
      } else {
        onAuthenticated(result.user, redirect);
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setQuickLoading(false);
    }
  }

  async function resendVerification() {
    if (!emailValid || resending) return;
    setResending(true);
    setError(null);
    setInfo(null);
    try {
      const result = await api.resendVerification(email.trim(), redirect);
      if (result.dev_verify_url) {
        setDevLink(result.dev_verify_url);
        setInfo('验证邮件已重新发送。当前为开发邮件模式，可直接使用下方链接。');
      } else {
        setInfo('验证邮件已重新发送，请查收邮箱。');
      }
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setResending(false);
    }
  }

  async function copyPassword(value: string) {
    if (await copyText(value)) {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    }
  }

  function googleLogin() {
    if (!providers?.google) return;
    window.location.href = api.googleStartUrl(redirect);
  }

  function backToEmail() {
    setStep('email');
    setPassword('');
    setError(null);
    setInfo(null);
    setUnverified(false);
  }

  return (
    <>
      <AuthShell
        onBack={step === 'password' ? backToEmail : undefined}
        backLabel="返回"
      >
        <div className="text-center">
          <h1 className="text-[24px] font-semibold tracking-[-0.4px] text-ink-95">
            {step === 'password' ? '欢迎回来' : '登录或注册'}
          </h1>
          <p className="mt-2 text-[14px] text-ink-55">
            {step === 'password' ? '输入密码以登录' : '开始使用 Atoms 创作'}
          </p>
        </div>

        <div className="mt-6 space-y-3">
          {error ? <AuthAlert>{error}</AuthAlert> : null}
          {info ? <AuthAlert kind="success">{info}</AuthAlert> : null}
          {devLink ? (
            <a
              href={devLink}
              className="block break-all rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-[12px] leading-5 text-brand-600 underline"
            >
              开发模式验证链接：{devLink}
            </a>
          ) : null}

          {step === 'email' ? (
            <>
              <GoogleButton
                onClick={googleLogin}
                disabled={!providers?.google}
              />

              <AuthDivider />

              <form onSubmit={submitEmail} className="space-y-3">
                <input
                  type="email"
                  name="email"
                  value={email}
                  autoComplete="email"
                  placeholder="输入你的电子邮件地址"
                  onChange={(event) => setEmail(event.target.value)}
                  onBlur={() => setEmailTouched(true)}
                  className={authInputClass}
                />
                {showEmailError ? (
                  <p className="text-[11px] text-danger">
                    请输入有效的邮箱地址
                  </p>
                ) : null}
                <AuthLegalNote />
                <button
                  type="submit"
                  disabled={!emailValid || loading}
                  className={authPrimaryClass}
                >
                  {loading ? <Spinner size={15} /> : '继续'}
                </button>
              </form>

              {providers?.quick ? (
                <div className="space-y-2 pt-0.5">
                  <button
                    type="button"
                    onClick={quickLogin}
                    disabled={!emailValid || quickLoading || loading}
                    className={authSecondaryClass}
                  >
                    {quickLoading ? (
                      <Spinner size={15} />
                    ) : (
                      <Sparkle size={15} />
                    )}
                    快捷注册登录（演示）
                  </button>
                  <div className="rounded-lg border border-line-6 bg-[#FAFAF9] px-3 py-2.5 text-left">
                    <p className="text-[11px] font-medium leading-[18px] text-ink-55">
                      Tips：快捷注册登录（演示）介绍
                    </p>
                    <ul className="mt-0.5 space-y-0.5 text-[11px] leading-[18px] text-ink-30">
                      <li>1. 用于演示，跳过注册登录认证</li>
                      <li>
                        2. 新账号自动创建，默认密码{' '}
                        <span className="font-mono text-ink-55">
                          {quickPassword}
                        </span>
                      </li>
                      <li>3. 已有账号免密直接登录</li>
                    </ul>
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <>
              <form onSubmit={submitPassword} className="space-y-4">
                <AuthField label="邮箱">
                  <input
                    type="email"
                    value={email}
                    readOnly
                    className={`${authInputClass} bg-[#F2F2F0] text-ink-55`}
                  />
                </AuthField>
                <AuthField label="密码">
                  <PasswordInput
                    value={password}
                    onChange={setPassword}
                    autoFocus
                  />
                </AuthField>

                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={() =>
                      onNavigate(
                        `/password/forgot?email=${encodeURIComponent(email.trim())}`,
                      )
                    }
                    className="text-[12px] text-brand-600 transition hover:underline"
                  >
                    忘记密码？
                  </button>
                </div>

                <button
                  type="submit"
                  disabled={!password || loading}
                  className={authPrimaryClass}
                >
                  {loading ? <Spinner size={15} /> : '继续'}
                </button>
              </form>

              {unverified ? (
                <button
                  type="button"
                  onClick={resendVerification}
                  disabled={resending}
                  className={authSecondaryClass}
                >
                  {resending ? <Spinner size={15} /> : null}
                  重新发送验证邮件
                </button>
              ) : null}

              <button
                type="button"
                onClick={backToEmail}
                className="w-full text-center text-[12px] text-ink-55 transition hover:text-ink-95"
              >
                返回
              </button>
            </>
          )}
        </div>
      </AuthShell>

      {created ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 px-4">
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="quick-created-title"
            className="w-full max-w-[392px] animate-rise rounded-2xl bg-white p-6 shadow-[0_30px_90px_rgba(12,12,12,0.28)]"
          >
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-50 text-brand">
              <Sparkle size={20} />
            </div>
            <h2
              id="quick-created-title"
              className="mt-4 text-[20px] font-semibold tracking-[-0.3px] text-ink-95"
            >
              账号已创建
            </h2>
            <p className="mt-2 text-[13px] leading-6 text-ink-55">
              我们已用默认密码为你创建账号并自动登录。之后也可以回到登录页，用邮箱
              + 密码登录。
            </p>

            <div className="mt-5 space-y-2 rounded-xl border border-line-6 bg-[#FAFAF9] p-3">
              <div className="flex items-center gap-2 text-[12px]">
                <span className="w-16 flex-none text-ink-30">邮箱</span>
                <span className="truncate text-ink-95">{email.trim()}</span>
              </div>
              <div className="flex items-center gap-2 text-[12px]">
                <span className="w-16 flex-none text-ink-30">默认密码</span>
                <span className="font-mono text-ink-95">
                  {created.password}
                </span>
                <button
                  type="button"
                  onClick={() => void copyPassword(created.password)}
                  title="复制密码"
                  className="ml-auto flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-brand-600 transition hover:bg-brand-50"
                >
                  <Copy size={13} />
                  {copied ? '已复制' : '复制'}
                </button>
              </div>
            </div>

            <button
              type="button"
              onClick={() => onAuthenticated(created.user, redirect)}
              className={`${authPrimaryClass} mt-5`}
            >
              进入工作台
            </button>
            <p className="mt-3 text-center text-[11px] leading-5 text-ink-30">
              演示环境提示：该密码也会显示在快捷登录按钮下方。
            </p>
          </div>
        </div>
      ) : null}
    </>
  );
}
