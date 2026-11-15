import type { Project, ProjectMode, ProjectStatus } from '../types';
import {
  MODE_LABEL,
  STATUS_LABEL,
  STATUS_TONE,
  absoluteUrl,
  coverFor,
} from '../lib/projects';
import { AtomsMark, Check, Copy, ExternalLink, Spinner } from './Icons';

interface Props {
  project: Project;
  status: ProjectStatus;
  mode: ProjectMode;
  latestVersion: number;
  building: boolean;
  busy: boolean;
  copied: boolean;
  error?: string | null;
  onOpenPublish: () => void;
  onPause: () => void;
  onResume: () => void;
  onCopyUrl: () => void;
  onOpenSite: () => void;
}

function formatTime(iso?: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function resourceLabel(mode: ProjectMode): string {
  if (mode === 'frontend') return '纯前端静态站点';
  if (mode === 'backend') return 'FastAPI + SQLite';
  return 'React + FastAPI + SQLite';
}

function dataLabel(mode: ProjectMode): string {
  return mode === 'frontend' ? '浏览器本地存储' : '项目独立 SQLite';
}

export default function OverviewPane({
  project,
  status,
  mode,
  latestVersion,
  building,
  busy,
  copied,
  error,
  onOpenPublish,
  onPause,
  onResume,
  onCopyUrl,
  onOpenSite,
}: Props) {
  const publishedUrl = absoluteUrl(project.published_url);
  const builtVersion = project.built_version ?? null;
  const publishedVersion = project.published_version ?? null;
  const hasChanges =
    project.has_changes ??
    (publishedVersion !== null &&
      builtVersion !== null &&
      builtVersion > publishedVersion);
  const disabled = busy || building;

  return (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-base pb-2 pr-2">
      <div className="min-h-0 flex-1 overflow-y-auto rounded-[16px] bg-base">
        <div className="mx-auto w-full max-w-[920px] px-4 py-5 sm:px-8 sm:py-7">
          <header className="flex items-start gap-4 rounded-2xl border border-line-6 bg-white p-5">
            <div
              className="grid h-14 w-14 flex-none place-items-center rounded-2xl border border-white/70"
              style={{ background: coverFor(project.id) }}
            >
              <AtomsMark size={26} className="text-brand-text" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="min-w-0 truncate text-[20px] font-medium text-ink-95">
                  {project.name || '未命名项目'}
                </h2>
                <span
                  className={`inline-flex flex-none items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_TONE[status].badge}`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${STATUS_TONE[status].dot}`}
                  />
                  {STATUS_LABEL[status]}
                </span>
              </div>
              <p className="mt-1.5 text-[12px] text-ink-55">
                {MODE_LABEL[mode]}应用 · 当前 v{latestVersion || builtVersion || 1}
                {publishedVersion !== null ? ` · 线上 v${publishedVersion}` : ''}
              </p>

              {publishedUrl ? (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <code className="max-w-full truncate rounded-lg bg-line-4 px-2.5 py-1 font-mono text-[11px] text-ink-80">
                    {publishedUrl.replace(/^https?:\/\//, '')}
                  </code>
                  <button
                    type="button"
                    onClick={onCopyUrl}
                    className="inline-flex h-7 items-center gap-1 rounded-full border border-line-6 bg-white px-2.5 text-[11px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95"
                  >
                    {copied ? <Check size={13} /> : <Copy size={13} />}
                    {copied ? '已复制' : '复制'}
                  </button>
                  <button
                    type="button"
                    onClick={onOpenSite}
                    disabled={status === 'paused'}
                    title={
                      status === 'paused' ? '恢复在线后可访问' : '在新标签页打开'
                    }
                    className="inline-flex h-7 items-center gap-1 rounded-full border border-line-6 bg-white px-2.5 text-[11px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    <ExternalLink size={13} />
                    打开
                  </button>
                </div>
              ) : (
                <p className="mt-3 text-[12px] text-ink-55">
                  发布后会生成一个公开访问链接。
                </p>
              )}
            </div>
          </header>

          {error ? (
            <p className="mt-3 rounded-xl bg-danger/10 px-4 py-2.5 text-[12px] leading-[18px] text-danger">
              {error}
            </p>
          ) : null}

          {hasChanges ? (
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-warning/20 bg-warning/10 px-5 py-4">
              <div className="min-w-0">
                <p className="text-[13px] font-medium text-warning">
                  线上有未发布的变更
                </p>
                <p className="mt-1 text-[12px] leading-[19px] text-ink-80">
                  工作台已构建 v{builtVersion ?? '—'}，线上仍是 v
                  {publishedVersion ?? '—'}。发布后访客才能看到新版本。
                </p>
              </div>
              <button
                type="button"
                onClick={onOpenPublish}
                disabled={disabled}
                className="inline-flex h-9 flex-none items-center gap-1.5 rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {building ? <Spinner size={13} /> : null}
                {building ? '构建中…' : '发布新变更'}
              </button>
            </div>
          ) : null}

          {status === 'unpublished' ? (
            <section className="mt-4 rounded-2xl border border-line-6 bg-white p-6">
              <h3 className="text-[18px] font-medium text-ink-95">
                发布你的 app
              </h3>
              <p className="mt-2 max-w-[640px] text-[13px] leading-[21px] text-ink-55">
                发布后，任何人都可以通过公开链接访问。上线后你仍然可以继续编辑；
                工作台的新构建不会影响线上，直到你重新发布。
              </p>
              <button
                type="button"
                onClick={onOpenPublish}
                disabled={disabled}
                className="mt-5 inline-flex h-10 items-center gap-1.5 rounded-full bg-brand px-5 text-[13px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {building ? <Spinner size={14} /> : null}
                {building ? '构建中…' : '发布应用'}
              </button>

              <div className="mt-6 grid gap-3 sm:grid-cols-2">
                <InfoCard
                  title="线上应用版本"
                  value={builtVersion ? `v${builtVersion}` : '—'}
                  hint="当前构建成功、可供发布的版本"
                />
                <InfoCard
                  title="访问地址"
                  value="发布后生成"
                  hint="由平台分配，无需配置 DNS"
                />
                <InfoCard
                  title="生产资源"
                  value={resourceLabel(mode)}
                  hint="构建产物由共享 esbuild 工具链生成"
                />
                <InfoCard
                  title="数据存储"
                  value={dataLabel(mode)}
                  hint={
                    mode === 'frontend'
                      ? '数据保存在访客浏览器中'
                      : 'backend/data/app.db · 线上与工作台共用'
                  }
                />
              </div>
            </section>
          ) : (
            <section className="mt-6">
              <h3 className="text-[13px] font-medium text-ink-95">管理</h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-line-6 bg-white p-5">
                  <p className="text-[13px] font-medium text-ink-95">应用状态</p>
                  <p className="mt-1.5 text-[12px] leading-[19px] text-ink-55">
                    {status === 'online'
                      ? '访客可以通过公开链接访问这个应用。'
                      : '站点已暂停，访客无法访问；恢复不需要重新构建。'}
                  </p>
                  <button
                    type="button"
                    onClick={status === 'online' ? onPause : onResume}
                    disabled={busy}
                    className={`mt-3 inline-flex h-8 items-center gap-1.5 rounded-full border px-3 text-[12px] font-medium transition disabled:cursor-not-allowed disabled:opacity-40 ${
                      status === 'online'
                        ? 'border-line-6 bg-white text-ink-80 hover:border-line-12 hover:text-ink-95'
                        : 'border-brand bg-brand text-white hover:bg-brand-600'
                    }`}
                  >
                    {busy ? <Spinner size={13} /> : null}
                    {status === 'online' ? '暂停访问' : '恢复在线'}
                  </button>
                </div>

                <div className="rounded-2xl border border-line-6 bg-white p-5">
                  <p className="text-[13px] font-medium text-ink-95">线上版本</p>
                  <p className="mt-2 text-[22px] font-medium leading-none text-ink-95">
                    v{publishedVersion ?? '—'}
                  </p>
                  <p className="mt-1.5 text-[11px] text-ink-55">
                    {project.published_at
                      ? `发布于 ${formatTime(project.published_at)}`
                      : '尚未发布'}
                  </p>
                </div>

                <div className="rounded-2xl border border-line-6 bg-white p-5">
                  <p className="text-[13px] font-medium text-ink-95">当前构建</p>
                  <p className="mt-2 text-[22px] font-medium leading-none text-ink-95">
                    v{builtVersion ?? '—'}
                  </p>
                  <p className="mt-1.5 text-[11px] text-ink-55">
                    {project.built_at
                      ? `构建于 ${formatTime(project.built_at)}`
                      : '还没有成功构建'}
                    {hasChanges ? ' · 与线上不一致' : ' · 与线上一致'}
                  </p>
                </div>

                <div className="rounded-2xl border border-line-6 bg-white p-5">
                  <p className="text-[13px] font-medium text-ink-95">生产资源</p>
                  <p className="mt-2 text-[13px] font-medium text-ink-95">
                    {resourceLabel(mode)}
                  </p>
                  <p className="mt-1.5 text-[11px] leading-[17px] text-ink-55">
                    {mode === 'frontend'
                      ? '静态资源由平台托管 · 无需后端进程'
                      : '数据保存在项目独立 SQLite · 发布运行时与工作台隔离'}
                  </p>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}

function InfoCard({
  title,
  value,
  hint,
}: {
  title: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-line-4 bg-[#FBFBFA] px-4 py-3.5">
      <p className="text-[11px] font-medium text-ink-55">{title}</p>
      <p className="mt-1 truncate text-[13px] font-medium text-ink-95">
        {value}
      </p>
      <p className="mt-1 text-[11px] leading-[17px] text-ink-55">{hint}</p>
    </div>
  );
}
