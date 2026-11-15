import { useEffect } from 'react';
import type { Project, ProjectStatus } from '../types';
import {
  DISCOVER_CATEGORIES,
  isDiscoverCategory,
} from '../lib/discover';
import { absoluteUrl } from '../lib/projects';
import { Check, Copy, ExternalLink, Sparkle, Spinner, X } from './Icons';

interface Props {
  open: boolean;
  project: Project;
  status: ProjectStatus;
  building: boolean;
  busy: boolean;
  error: string | null;
  copied: boolean;
  description: string;
  category: string;
  suggestingCategory: boolean;
  onDescriptionChange: (value: string) => void;
  onCategoryChange: (value: string) => void;
  onSuggestCategory: () => void;
  onClose: () => void;
  onPublish: () => void;
  onPause: () => void;
  onResume: () => void;
  onOpenSite: () => void;
  onCopyUrl: () => void;
}

export default function PublishDialog({
  open,
  project,
  status,
  building,
  busy,
  error,
  copied,
  description,
  category,
  suggestingCategory,
  onDescriptionChange,
  onCategoryChange,
  onSuggestCategory,
  onClose,
  onPublish,
  onPause,
  onResume,
  onOpenSite,
  onCopyUrl,
}: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  if (!open) return null;

  const built = project.built_version ?? null;
  const published = project.published_version ?? null;
  const hasChanges =
    project.has_changes ??
    (published !== null && built !== null && built > published);
  const publicUrl = absoluteUrl(project.published_url);
  const futureUrl = absoluteUrl(`/s/${project.id}/`);
  const disabled = busy || building;

  const content = (() => {
    if (status === 'draft') {
      return {
        title: '还没有可发布的内容',
        body: '先在左侧对话里描述你的需求。首次构建成功后，这里就会出现发布入口。',
        primary: null,
      };
    }
    if (status === 'unpublished') {
      return {
        title: '发布你的 app',
        body: '发布后，任何人都可以通过公开链接访问。上线后你仍然可以继续编辑；工作台后续的新构建不会影响线上，直到你再次发布。',
        primary: '发布应用',
      };
    }
    if (status === 'online' && !hasChanges) {
      return {
        title: '项目已在线',
        body: `线上已是最新版本 v${published ?? '—'}，访客可以通过公开链接访问。`,
        primary: null,
      };
    }
    if (status === 'online' && hasChanges) {
      return {
        title: '发布新变更',
        body: `工作台已构建 v${built ?? '—'}，线上仍是 v${published ?? '—'}。更新后访客会立即看到新版本。`,
        primary: '更新线上',
      };
    }
    if (status === 'paused' && !hasChanges) {
      return {
        title: '站点已暂停',
        body: '访客目前无法访问这个应用。恢复在线不需要重新构建。',
        primary: null,
      };
    }
    return {
      title: '发布新变更',
      body: `工作台已构建 v${built ?? '—'}，线上仍是 v${published ?? '—'}。更新后站点仍保持暂停，恢复在线后访客才能看到新版本。`,
      primary: '更新线上',
    };
  })();

  const canPublish = Boolean(content.primary);
  const selectedCategory = isDiscoverCategory(category) ? category : '其他';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
      <button
        type="button"
        aria-label="关闭弹窗"
        onClick={onClose}
        className="absolute inset-0 cursor-default bg-[rgba(12,12,12,0.32)] animate-fade backdrop-blur-[2px]"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="publish-dialog-title"
        className="relative max-h-[calc(100vh-32px)] w-full max-w-[520px] overflow-y-auto rounded-2xl border border-line-6 bg-white shadow-float animate-rise"
      >
        <div className="flex items-start justify-between gap-4 px-6 pt-5">
          <div className="min-w-0">
            <h2
              id="publish-dialog-title"
              className="text-[17px] font-medium text-ink-95"
            >
              {content.title}
            </h2>
            <p className="mt-2 text-[13px] leading-[21px] text-ink-55">
              {content.body}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="关闭"
            className="grid h-7 w-7 flex-none place-items-center rounded-full text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
          >
            <X size={15} />
          </button>
        </div>

        <div className="mt-4 space-y-2 px-6">
          {status !== 'draft' ? (
            <div className="flex items-center justify-between gap-3 rounded-xl bg-line-4 px-3.5 py-2.5">
              <span className="text-[11px] text-ink-55">版本</span>
              <span className="text-[12px] font-medium text-ink-95">
                {published !== null ? `线上 v${published}` : '尚未发布'}
                {built !== null ? ` · 工作台 v${built}` : ''}
              </span>
            </div>
          ) : null}

          {status === 'unpublished' ? (
            <div className="flex items-center justify-between gap-3 rounded-xl bg-line-4 px-3.5 py-2.5">
              <span className="text-[11px] text-ink-55">访问地址</span>
              <span className="max-w-[300px] truncate font-mono text-[11px] text-ink-80">
                发布后生成
              </span>
            </div>
          ) : null}

          {publicUrl ? (
            <div className="flex items-center gap-2 rounded-xl bg-line-4 px-3.5 py-2.5">
              <span className="flex-none text-[11px] text-ink-55">访问地址</span>
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-ink-80">
                {publicUrl.replace(/^https?:\/\//, '')}
              </span>
              <button
                type="button"
                onClick={onCopyUrl}
                className="inline-flex h-6 flex-none items-center gap-1 rounded-full bg-white px-2 text-[10px] font-medium text-ink-80 transition hover:text-ink-95"
              >
                {copied ? <Check size={12} /> : <Copy size={12} />}
                {copied ? '已复制' : '复制'}
              </button>
            </div>
          ) : null}

          {status === 'unpublished' && futureUrl ? (
            <p className="px-0.5 text-[11px] leading-[17px] text-ink-55">
              发布后地址形如{' '}
              <span className="font-mono text-ink-80">
                {futureUrl.replace(/^https?:\/\//, '')}
              </span>
              ，届时才可访问。
            </p>
          ) : null}

          {status === 'paused' && hasChanges ? (
            <p className="px-0.5 text-[11px] leading-[17px] text-ink-55">
              更新线上不会自动恢复访问；需要恢复时请点击「恢复在线」。
            </p>
          ) : null}

          {canPublish ? (
            <div className="space-y-3 rounded-xl border border-line-4 bg-[#FBFBFA] p-3.5">
              <label className="block">
                <span className="flex items-center justify-between text-[11px] text-ink-55">
                  <span>简介（可选）</span>
                  <span>{description.length}/280</span>
                </span>
                <textarea
                  value={description}
                  onChange={(event) =>
                    onDescriptionChange(event.target.value.slice(0, 280))
                  }
                  disabled={disabled}
                  rows={3}
                  maxLength={280}
                  placeholder="一句话介绍这个应用，会显示在发现详情页。"
                  className="mt-1.5 w-full resize-none rounded-lg border border-line-8 bg-white px-3 py-2 text-[12px] leading-[19px] text-ink-95 outline-none transition placeholder:text-ink-30 focus:border-line-12 disabled:cursor-not-allowed disabled:opacity-60"
                />
              </label>

              <div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] text-ink-55">分类</span>
                  <button
                    type="button"
                    onClick={onSuggestCategory}
                    disabled={disabled || suggestingCategory}
                    className="inline-flex h-6 items-center gap-1 rounded-full border border-line-8 bg-white px-2 text-[10px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {suggestingCategory ? (
                      <Spinner size={11} />
                    ) : (
                      <Sparkle size={11} />
                    )}
                    自动识别
                  </button>
                </div>
                <select
                  aria-label="分类"
                  value={selectedCategory}
                  onChange={(event) => onCategoryChange(event.target.value)}
                  disabled={disabled}
                  className="mt-1.5 h-9 w-full rounded-lg border border-line-8 bg-white px-2.5 text-[12px] text-ink-95 outline-none transition focus:border-line-12 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {DISCOVER_CATEGORIES.map((item) => (
                    <option key={item} value={item}>
                      {item}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-[10px] leading-[16px] text-ink-30">
                  分类会显示在发现页，自动识别只给建议，你可以随时修改。
                </p>
              </div>
            </div>
          ) : null}

          {error ? (
            <p className="rounded-lg bg-danger/10 px-3 py-2 text-[12px] leading-[18px] text-danger">
              {error}
            </p>
          ) : null}
        </div>

        <div className="mt-5 flex flex-wrap items-center justify-end gap-2 border-t border-line-4 bg-[#FBFBFA] px-6 py-4">
          {status === 'draft' ? (
            <button
              type="button"
              onClick={onClose}
              className="inline-flex h-9 items-center rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600"
            >
              知道了
            </button>
          ) : null}

          {status === 'unpublished' ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-9 items-center rounded-full border border-line-6 bg-white px-4 text-[12px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95"
              >
                取消
              </button>
              <button
                type="button"
                onClick={onPublish}
                disabled={disabled}
                className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? <Spinner size={13} /> : null}
                {building ? '构建中…' : busy ? '发布中…' : content.primary}
              </button>
            </>
          ) : null}

          {status === 'online' && !hasChanges ? (
            <>
              <button
                type="button"
                onClick={onPause}
                disabled={busy}
                className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line-6 bg-white px-4 text-[12px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? <Spinner size={13} /> : null}
                暂停访问
              </button>
              <button
                type="button"
                onClick={onOpenSite}
                className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600"
              >
                <ExternalLink size={13} />
                打开站点
              </button>
            </>
          ) : null}

          {status === 'online' && hasChanges ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-9 items-center rounded-full border border-line-6 bg-white px-4 text-[12px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95"
              >
                取消
              </button>
              <button
                type="button"
                onClick={onPublish}
                disabled={disabled}
                className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? <Spinner size={13} /> : null}
                {building ? '构建中…' : busy ? '发布中…' : content.primary}
              </button>
            </>
          ) : null}

          {status === 'paused' && !hasChanges ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-9 items-center rounded-full border border-line-6 bg-white px-4 text-[12px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95"
              >
                关闭
              </button>
              <button
                type="button"
                onClick={onResume}
                disabled={busy}
                className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? <Spinner size={13} /> : null}
                恢复在线
              </button>
            </>
          ) : null}

          {status === 'paused' && hasChanges ? (
            <>
              <button
                type="button"
                onClick={onClose}
                className="inline-flex h-9 items-center rounded-full border border-line-6 bg-white px-4 text-[12px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95"
              >
                取消
              </button>
              <button
                type="button"
                onClick={onResume}
                disabled={busy}
                className="inline-flex h-9 items-center rounded-full border border-line-6 bg-white px-4 text-[12px] font-medium text-ink-80 transition hover:border-line-12 hover:text-ink-95 disabled:cursor-not-allowed disabled:opacity-40"
              >
                恢复在线
              </button>
              <button
                type="button"
                onClick={onPublish}
                disabled={disabled}
                className="inline-flex h-9 items-center gap-1.5 rounded-full bg-brand px-4 text-[12px] font-medium text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {busy ? <Spinner size={13} /> : null}
                {building ? '构建中…' : busy ? '发布中…' : content.primary}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
