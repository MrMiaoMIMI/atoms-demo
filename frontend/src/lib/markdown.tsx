import type { ReactNode } from "react";
import { useMemo } from "react";

type Block =
  | { type: "p"; lines: string[] }
  | { type: "h"; level: number; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[] }
  | { type: "quote"; lines: string[] }
  | { type: "code"; lang: string; text: string }
  | { type: "hr" };

function parseBlocks(content: string): Block[] {
  const lines = content.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];
  let index = 0;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "p", lines: paragraph });
      paragraph = [];
    }
  };

  while (index < lines.length) {
    const line = lines[index];

    if (line.trimStart().startsWith("```")) {
      flushParagraph();
      const lang = line.trim().slice(3).trim();
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trimStart().startsWith("```")) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      blocks.push({ type: "code", lang, text: body.join("\n") });
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      index += 1;
      continue;
    }

    if (/^\s*(---|\*\*\*|___)\s*$/.test(line)) {
      flushParagraph();
      blocks.push({ type: "hr" });
      index += 1;
      continue;
    }

    const heading = /^(#{1,4})\s+(.*)$/.exec(line);
    if (heading) {
      flushParagraph();
      blocks.push({ type: "h", level: heading[1].length, text: heading[2].trim() });
      index += 1;
      continue;
    }

    if (/^\s*>\s?/.test(line)) {
      flushParagraph();
      const quote: string[] = [];
      while (index < lines.length && /^\s*>\s?/.test(lines[index])) {
        quote.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      blocks.push({ type: "quote", lines: quote });
      continue;
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length && /^\s*[-*+]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*[-*+]\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "ul", items });
      continue;
    }

    if (/^\s*\d+[.)]\s+/.test(line)) {
      flushParagraph();
      const items: string[] = [];
      while (index < lines.length && /^\s*\d+[.)]\s+/.test(lines[index])) {
        items.push(lines[index].replace(/^\s*\d+[.)]\s+/, ""));
        index += 1;
      }
      blocks.push({ type: "ol", items });
      continue;
    }

    paragraph.push(line);
    index += 1;
  }

  flushParagraph();
  return blocks;
}

const INLINE = /(\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*|`[^`\n]+`|\[[^\]]+\]\([^)\s]+\)|@[\w一-龥]+)/g;

function inline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let match: RegExpExecArray | null;
  INLINE.lastIndex = 0;

  while ((match = INLINE.exec(text)) !== null) {
    if (match.index > last) nodes.push(text.slice(last, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${match.index}`;

    if (token.startsWith("**") || token.startsWith("__")) {
      nodes.push(
        <strong key={key} className="font-medium text-ink-95">
          {token.slice(2, -2)}
        </strong>
      );
    } else if (token.startsWith("`")) {
      nodes.push(
        <code
          key={key}
          className="rounded-[4px] bg-line-6 px-1.5 py-0.5 font-mono text-[12.5px] text-ink-80"
        >
          {token.slice(1, -1)}
        </code>
      );
    } else if (token.startsWith("[")) {
      const link = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(token);
      if (link && /^(https?:\/\/|mailto:)/i.test(link[2])) {
        nodes.push(
          <a
            key={key}
            href={link[2]}
            target="_blank"
            rel="noreferrer"
            className="text-brand-text underline decoration-brand/30 underline-offset-2 hover:decoration-brand"
          >
            {link[1]}
          </a>
        );
      } else {
        nodes.push(token);
      }
    } else if (token.startsWith("@")) {
      nodes.push(
        <span
          key={key}
          className="mx-0.5 inline-flex items-center rounded-[6px] bg-brand-50 px-1.5 py-0.5 text-[12px] font-medium leading-[18px] text-brand-text"
        >
          {token}
        </span>
      );
    } else if (token.startsWith("*")) {
      nodes.push(
        <em key={key} className="italic">
          {token.slice(1, -1)}
        </em>
      );
    } else {
      nodes.push(token);
    }
    last = match.index + token.length;
  }

  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

function paragraphNodes(lines: string[], keyPrefix: string): ReactNode[] {
  return lines.map((line, index) => (
    <span key={`${keyPrefix}-l-${index}`}>
      {inline(line, `${keyPrefix}-${index}`)}
      {index < lines.length - 1 ? <br /> : null}
    </span>
  ));
}

export function Markdown({ content, className = "" }: { content: string; className?: string }) {
  const blocks = useMemo(() => parseBlocks(content), [content]);

  return (
    <div className={`text-[16px] leading-[24px] text-ink-80 ${className}`}>
      {blocks.map((block, index) => {
        const key = `b-${index}`;
        if (block.type === "code") {
          return (
            <pre
              key={key}
              className="my-3 overflow-x-auto rounded-[10px] border border-line-6 bg-[#F7F7F6] p-3 font-mono text-[12.5px] leading-[20px] text-ink-80"
            >
              <code>{block.text}</code>
            </pre>
          );
        }
        if (block.type === "h") {
          const size =
            block.level <= 1
              ? "text-[20px] leading-[28px]"
              : block.level === 2
                ? "text-[18px] leading-[26px]"
                : "text-[16px] leading-[24px]";
          return (
            <p key={key} className={`mb-2 mt-4 font-medium text-ink-95 first:mt-0 ${size}`}>
              {inline(block.text, key)}
            </p>
          );
        }
        if (block.type === "ul") {
          return (
            <ul key={key} className="my-2 list-disc space-y-1 pl-5 marker:text-ink-30">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{inline(item, `${key}-${itemIndex}`)}</li>
              ))}
            </ul>
          );
        }
        if (block.type === "ol") {
          return (
            <ol key={key} className="my-2 list-decimal space-y-1 pl-5 marker:text-ink-30">
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-${itemIndex}`}>{inline(item, `${key}-${itemIndex}`)}</li>
              ))}
            </ol>
          );
        }
        if (block.type === "quote") {
          return (
            <blockquote
              key={key}
              className="my-3 border-l-2 border-line-12 pl-3 text-ink-55"
            >
              {paragraphNodes(block.lines, key)}
            </blockquote>
          );
        }
        if (block.type === "hr") {
          return <hr key={key} className="my-4 border-line-6" />;
        }
        return (
          <p key={key} className="mb-3 last:mb-0">
            {paragraphNodes(block.lines, key)}
          </p>
        );
      })}
    </div>
  );
}
