import type { ChangeEvent, ReactNode } from 'react';
import { useState } from 'react';
import { AtomsMark, CheckCircleFill, ChevronLeft, Eye, EyeOff } from '../Icons';

const BULLETS = [
  '几分钟而不是几周',
  '真实应用，不只是演示',
  '多智能体协作生成',
  '前后端与数据库按需生成',
  '代码可导出，数据可持久化',
];

export const authInputClass =
  'h-10 w-full rounded-lg border border-line-6 bg-[#F7F7F6] px-3 text-[14px] text-ink-95 outline-none transition placeholder:text-ink-30 focus:border-brand focus:bg-white focus:ring-2 focus:ring-brand/10 disabled:cursor-not-allowed disabled:text-ink-55';

export const authPrimaryClass =
  'flex h-10 w-full items-center justify-center rounded-lg bg-brand text-[14px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:bg-brand-200 disabled:text-white';

export const authSecondaryClass =
  'flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-brand-200 bg-brand-50 text-[13px] font-medium text-brand-600 transition hover:bg-brand-100 disabled:cursor-not-allowed disabled:border-line-6 disabled:bg-transparent disabled:text-ink-30';

function GoogleG({ size = 17 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#FFC107"
        d="M43.6 20.5H42V20H24v8h11.3C33.7 32.7 29.3 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 12.9 4 4 12.9 4 24s8.9 20 20 20 20-8.9 20-20c0-1.2-.1-2.4-.4-3.5z"
      />
      <path
        fill="#FF3D00"
        d="m6.3 14.7 6.6 4.8C14.7 15.1 18.9 12 24 12c3.1 0 5.9 1.2 8 3.1l5.7-5.7C34.1 6.1 29.3 4 24 4 16.3 4 9.7 8.3 6.3 14.7z"
      />
      <path
        fill="#4CAF50"
        d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-7.9l-6.5 5C9.5 39.6 16.2 44 24 44z"
      />
      <path
        fill="#1976D2"
        d="M43.6 20.5H42V20H24v8h11.3c-.8 2.2-2.2 4.2-4.1 5.6l6.2 5.2C41.4 35.3 44 30.2 44 24c0-1.2-.1-2.4-.4-3.5z"
      />
    </svg>
  );
}

export function GoogleButton({
  onClick,
  disabled = false,
  label = '使用 Google 继续',
  disabledReason,
}: {
  onClick?: () => void;
  disabled?: boolean;
  label?: string;
  disabledReason?: string | null;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={disabled ? disabledReason || 'Google 登录尚未配置' : undefined}
      className="flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-line-8 bg-white text-[13px] font-medium text-ink-95 transition hover:bg-[#FAFAF9] disabled:cursor-not-allowed disabled:text-ink-30 disabled:hover:bg-white"
    >
      <GoogleG />
      <span>{label}</span>
      {disabled ? (
        <span className="rounded-full border border-line-6 px-1.5 py-0.5 text-[10px] leading-none text-ink-30">
          不可用
        </span>
      ) : null}
    </button>
  );
}

export function AuthDivider() {
  return (
    <div className="my-4 flex items-center gap-3 text-[12px] text-ink-30">
      <span className="h-px flex-1 bg-line-6" />
      或
      <span className="h-px flex-1 bg-line-6" />
    </div>
  );
}

export function AuthField({
  label,
  hint,
  children,
}: {
  label?: string;
  hint?: ReactNode;
  children: ReactNode;
}) {
  return (
    <label className="block">
      {label ? (
        <span className="mb-1.5 block text-[12px] font-medium text-ink-55">
          {label}
        </span>
      ) : null}
      {children}
      {hint ? (
        <span className="mt-1.5 block text-[11px] leading-5 text-ink-30">
          {hint}
        </span>
      ) : null}
    </label>
  );
}

export function PasswordInput({
  value,
  onChange,
  placeholder = '输入你的密码',
  autoComplete = 'current-password',
  autoFocus = false,
  disabled = false,
  id,
}: {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  autoComplete?: string;
  autoFocus?: boolean;
  disabled?: boolean;
  id?: string;
}) {
  const [visible, setVisible] = useState(false);
  return (
    <div className="relative">
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        value={value}
        autoComplete={autoComplete}
        autoFocus={autoFocus}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event: ChangeEvent<HTMLInputElement>) =>
          onChange(event.target.value)
        }
        className={`${authInputClass} pr-10`}
      />
      <button
        type="button"
        onClick={() => setVisible((current) => !current)}
        title={visible ? '隐藏密码' : '显示密码'}
        aria-label={visible ? '隐藏密码' : '显示密码'}
        className="absolute right-1 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-ink-30 transition hover:bg-line-4 hover:text-ink-55"
      >
        {visible ? <EyeOff size={16} /> : <Eye size={16} />}
      </button>
    </div>
  );
}

export function AuthAlert({
  kind = 'error',
  children,
}: {
  kind?: 'error' | 'info' | 'success';
  children: ReactNode;
}) {
  const styles = {
    error: 'border-[#F3C6C4] bg-[#FFF5F4] text-[#B42318]',
    info: 'border-brand-200 bg-brand-50 text-brand-600',
    success: 'border-[#BFE5CE] bg-[#F1FAF5] text-[#1E7A45]',
  }[kind];
  return (
    <div
      className={`rounded-lg border px-3 py-2.5 text-[12px] leading-5 ${styles}`}
    >
      {children}
    </div>
  );
}

export function AuthLegalNote() {
  return (
    <p className="mt-2.5 text-center text-[11px] leading-5 text-ink-30">
      继续即表示你同意本演示项目的使用说明。
    </p>
  );
}

function BrandPanel() {
  return (
    <div className="relative flex h-full flex-col overflow-hidden rounded-[24px] bg-brand px-8 py-8 text-white">
      <div className="pointer-events-none absolute -right-20 top-1/4 h-72 w-72 rounded-full bg-white/10 blur-2xl" />
      <div className="pointer-events-none absolute -bottom-24 -left-20 h-72 w-72 rounded-full bg-[#9AB4FF]/20 blur-2xl" />

      <div className="relative flex items-center gap-2">
        <AtomsMark size={22} className="text-white" />
        <span className="text-[16px] font-medium tracking-[-0.2px]">Atoms</span>
      </div>

      <div className="relative mt-9 text-center">
        <h2 className="text-[30px] font-semibold leading-[1.2] tracking-[-0.6px]">
          把想法变成可运行的产品
        </h2>
        <ul className="mx-auto mt-7 w-fit space-y-3.5 text-left">
          {BULLETS.map((text) => (
            <li key={text} className="flex items-center gap-2 text-[18px] leading-[1.4]">
              <CheckCircleFill size={20} className="flex-none text-white/95" />
              <span className="text-white/95">{text}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="relative mt-auto pt-6">
        <div className="mx-auto w-[84%] rotate-[-2deg] rounded-2xl border border-white/20 bg-white/10 p-2.5 shadow-[0_20px_50px_rgba(0,0,0,0.2)] backdrop-blur">
          <div className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full bg-white/45" />
            <span className="h-1.5 w-1.5 rounded-full bg-white/30" />
            <span className="h-1.5 w-1.5 rounded-full bg-white/20" />
            <span className="ml-2 h-1.5 w-16 rounded-full bg-white/20" />
          </div>
          <div className="mt-2.5 rounded-xl bg-white p-3 text-ink-95">
            <div className="flex items-center gap-2">
              <span className="h-5 w-5 rounded-md bg-brand/15" />
              <span className="h-1.5 w-20 rounded-full bg-line-8" />
              <span className="ml-auto h-4 w-10 rounded-full bg-brand" />
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <span className="h-9 rounded-lg bg-brand-50" />
              <span className="h-9 rounded-lg bg-[#EEF7F0]" />
              <span className="h-9 rounded-lg bg-[#FFF4E8]" />
            </div>
            <div className="mt-2.5 space-y-1.5">
              <span className="block h-1.5 w-4/5 rounded-full bg-line-6" />
              <span className="block h-1.5 w-3/5 rounded-full bg-line-4" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AuthShell({
  children,
  onBack,
  backLabel = '返回',
}: {
  children: ReactNode;
  onBack?: () => void;
  backLabel?: string;
}) {
  return (
    <div className="flex min-h-screen bg-white">
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <div className="flex h-14 flex-none items-center px-5 sm:px-7">
          {onBack ? (
            <button
              type="button"
              onClick={onBack}
              className="flex items-center gap-1.5 rounded-md px-1.5 py-1 text-[13px] text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <ChevronLeft size={17} />
              {backLabel}
            </button>
          ) : (
            <span className="flex items-center gap-2 text-[15px] font-medium text-ink-95">
              <AtomsMark size={20} />
              Atoms
            </span>
          )}
        </div>

        <div className="flex flex-1 items-center justify-center px-5 pb-14">
          <div className="w-full max-w-[364px] animate-rise">{children}</div>
        </div>
      </div>

      <div className="hidden w-[45%] min-w-[460px] max-w-[660px] flex-none p-4 lg:block lg:h-screen">
        <BrandPanel />
      </div>
    </div>
  );
}
