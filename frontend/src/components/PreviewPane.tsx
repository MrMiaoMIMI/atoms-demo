import { useState } from 'react';
import type { ProjectMode } from '../types';
import {
  ApiIcon,
  AtomsMark,
  ExternalLink,
  Monitor,
  Refresh,
  Smartphone,
  Spinner,
} from './Icons';

interface Props {
  url: string | null;
  running: boolean;
  version: number;
  mode: ProjectMode;
  refreshKey: number;
  onRefresh: () => void;
}

export default function PreviewPane({
  url,
  running,
  version,
  mode,
  refreshKey,
  onRefresh,
}: Props) {
  const [device, setDevice] = useState<'desktop' | 'mobile'>('desktop');
  const src = url
    ? `${url}${url.includes('?') ? '&' : '?'}r=${refreshKey}`
    : null;

  return (
    <section className="relative flex min-h-0 min-w-0 flex-1 flex-col bg-base pb-2 pr-2">
      <div className="relative flex min-h-0 flex-1 items-stretch justify-center overflow-hidden rounded-[16px] bg-white">
        {src ? (
          <div
            className={`h-full transition-[width] duration-300 ease-out ${
              device === 'mobile'
                ? 'w-[390px] max-w-full border-x border-line-6 shadow-[0_0_40px_rgba(12,12,12,0.06)]'
                : 'w-full'
            }`}
          >
            <iframe
              key={src}
              src={src}
              title="生成应用预览"
              sandbox="allow-scripts allow-forms allow-popups allow-modals"
              className="h-full w-full border-0 bg-white"
            />
          </div>
        ) : (
          <div className="flex h-full w-full flex-col items-center justify-center gap-3 px-8 text-center">
            {mode === 'backend' && !running ? (
              <>
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-line-4 text-ink-55">
                  <ApiIcon size={22} />
                </span>
                <p className="text-[14px] font-medium text-ink-95">
                  纯 API 项目
                </p>
                <p className="max-w-[320px] text-[12px] leading-[19px] text-ink-55">
                  本轮只生成了 FastAPI + SQLite
                  接口，没有可预览页面。可以切换到「代码」查看 main.py
                  与数据库逻辑。
                </p>
              </>
            ) : (
              <>
                <span className="grid h-12 w-12 place-items-center rounded-2xl bg-line-4 text-brand">
                  {running ? <Spinner size={22} /> : <AtomsMark size={24} />}
                </span>
                <p className="text-[14px] font-medium text-ink-95">
                  {running ? 'Agent 正在构建你的应用…' : '应用会在这里实时运行'}
                </p>
                <p className="max-w-[320px] text-[12px] leading-[19px] text-ink-55">
                  {running
                    ? '构建完成会自动加载预览。'
                    : '在左侧描述需求，生成完成后这里会加载可交互的真实页面。'}
                </p>
              </>
            )}
          </div>
        )}

        {running && src ? (
          <div className="absolute right-3 top-3 inline-flex items-center gap-1.5 rounded-full border border-line-6 bg-white/95 px-3 py-1.5 text-[11px] text-ink-55 shadow-pill backdrop-blur">
            <Spinner size={12} className="text-brand" />
            更新中 · v{version || 1}
          </div>
        ) : null}

        {src ? (
          <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-0.5 rounded-full border border-line-4 bg-white/95 p-1 shadow-float backdrop-blur">
            <button
              type="button"
              onClick={() => setDevice('desktop')}
              title="桌面预览"
              className={`grid h-8 w-8 place-items-center rounded-full transition ${
                device === 'desktop'
                  ? 'bg-line-6 text-ink-95'
                  : 'text-ink-55 hover:text-ink-80'
              }`}
            >
              <Monitor size={16} />
            </button>
            <button
              type="button"
              onClick={() => setDevice('mobile')}
              title="移动预览"
              className={`grid h-8 w-8 place-items-center rounded-full transition ${
                device === 'mobile'
                  ? 'bg-line-6 text-ink-95'
                  : 'text-ink-55 hover:text-ink-80'
              }`}
            >
              <Smartphone size={16} />
            </button>
            <span className="mx-0.5 h-4 w-px bg-line-6" />
            <button
              type="button"
              onClick={onRefresh}
              title="刷新预览"
              className="grid h-8 w-8 place-items-center rounded-full text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <Refresh size={15} />
            </button>
            <a
              href={url ?? '#'}
              target="_blank"
              rel="noreferrer"
              title="在新标签页打开"
              className="grid h-8 w-8 place-items-center rounded-full text-ink-55 transition hover:bg-line-4 hover:text-ink-95"
            >
              <ExternalLink size={15} />
            </a>
          </div>
        ) : null}
      </div>
    </section>
  );
}
