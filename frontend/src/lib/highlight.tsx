import type { ReactNode } from "react";
import type { CodeLanguage } from "./files";

const CLASS = {
  comment: "text-[rgba(12,12,12,0.32)] italic",
  string: "text-[#25813C]",
  keyword: "text-[#895AF6]",
  number: "text-[#D87A16]",
  tag: "text-[#C9444A]",
  func: "text-[#425CE1]",
  key: "text-[#425CE1]",
  attr: "text-[#7341CC]",
} as const;

type TokenKind = keyof typeof CLASS;

const JS_RE =
  /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(\b(?:const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|class|extends|super|import|from|export|default|async|await|try|catch|finally|throw|typeof|instanceof|in|of|as|interface|type|enum|implements|static|public|private|protected|readonly|void|null|undefined|true|false|this)\b)|(\b\d[\d_]*(?:\.[\d_]+)?\b)|(<\/?[A-Za-z][\w.-]*)|([A-Za-z_$][\w$]*)(?=\s*\()/g;

const PY_RE =
  /(#.*$)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b(?:def|class|return|if|elif|else|for|while|in|not|and|or|import|from|as|with|try|except|finally|raise|pass|break|continue|lambda|yield|async|await|True|False|None|self|global|nonlocal|assert|del|is)\b)|(\b\d[\d_]*(?:\.[\d_]+)?\b)|(@[A-Za-z_][\w.]*)|([A-Za-z_][\w]*)(?=\s*\()/g;

const JSON_RE =
  /("(?:\\.|[^"\\])*")(?=\s*:)|("(?:\\.|[^"\\])*")|(-?\b\d[\d.eE+-]*\b)|(\b(?:true|false|null)\b)/g;

const CSS_RE =
  /(\/\*[\s\S]*?\*\/|<!--[\s\S]*?-->)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(#[0-9a-fA-F]{3,8}\b)|(\b\d+(?:\.\d+)?(?:px|rem|em|%|vh|vw|s|ms|fr)?\b)|([.#]?[A-Za-z-][\w-]*)(?=\s*[:{])/g;

const HTML_RE =
  /(<!--[\s\S]*?-->)|(<\/?[A-Za-z][\w:-]*|\/?>)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|([A-Za-z-]+)(?==)/g;

const SH_RE =
  /(#.*$)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b(?:if|then|else|fi|for|do|done|while|case|esac|function|export|local|return|echo|cd|set)\b)|(\b\d+\b)/g;

const SQL_RE =
  /(--.*$)|('(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")|(\b(?:select|from|where|insert|into|values|update|set|delete|create|table|index|primary|key|not|null|default|join|left|right|group|order|by|limit|as|and|or|text|integer|real|blob)\b)|(\b\d+(?:\.\d+)?\b)/gi;

function ruleFor(lang: CodeLanguage): RegExp | null {
  if (lang === "ts" || lang === "js") return JS_RE;
  if (lang === "py") return PY_RE;
  if (lang === "json") return JSON_RE;
  if (lang === "css") return CSS_RE;
  if (lang === "html") return HTML_RE;
  if (lang === "sh") return SH_RE;
  if (lang === "sql") return SQL_RE;
  return null;
}

function kindFor(lang: CodeLanguage, group: number): TokenKind | null {
  if (lang === "ts" || lang === "js") {
    return group === 1
      ? "comment"
      : group === 2
        ? "string"
        : group === 3
          ? "keyword"
          : group === 4
            ? "number"
            : group === 5
              ? "tag"
              : group === 6
                ? "func"
                : null;
  }
  if (lang === "py") {
    return group === 1
      ? "comment"
      : group === 2
        ? "string"
        : group === 3
          ? "keyword"
          : group === 4
            ? "number"
            : group === 5
              ? "func"
              : group === 6
                ? "func"
                : null;
  }
  if (lang === "json") {
    return group === 1 ? "key" : group === 2 ? "string" : group === 3 ? "number" : group === 4 ? "keyword" : null;
  }
  if (lang === "css") {
    return group === 1 ? "comment" : group === 2 ? "string" : group === 3 ? "number" : group === 4 ? "number" : group === 5 ? "attr" : null;
  }
  if (lang === "html") {
    return group === 1 ? "comment" : group === 2 ? "tag" : group === 3 ? "string" : group === 4 ? "attr" : null;
  }
  if (lang === "sh" || lang === "sql") {
    return group === 1 ? "comment" : group === 2 ? "string" : group === 3 ? "keyword" : group === 4 ? "number" : null;
  }
  return null;
}

export interface CodeToken {
  text: string;
  className?: string;
}

/** Split one line into syntax-colored tokens so the caller can overlay hits. */
export function tokenizeLine(line: string, lang: CodeLanguage): CodeToken[] {
  const rule = ruleFor(lang);
  if (!rule || !line) return [{ text: line || "\u00A0" }];
  rule.lastIndex = 0;

  const tokens: CodeToken[] = [];
  let last = 0;
  let match: RegExpExecArray | null;

  while ((match = rule.exec(line)) !== null) {
    if (match.index > last) tokens.push({ text: line.slice(last, match.index) });

    let kind: TokenKind | null = null;
    for (let group = 1; group < match.length; group += 1) {
      if (match[group] !== undefined) {
        kind = kindFor(lang, group);
        break;
      }
    }

    tokens.push({
      text: match[0],
      className: kind ? CLASS[kind] : undefined,
    });
    last = match.index + match[0].length;
    if (match[0].length === 0) rule.lastIndex += 1;
  }

  if (last < line.length) tokens.push({ text: line.slice(last) });
  return tokens.length ? tokens : [{ text: line }];
}

export function highlightLine(line: string, lang: CodeLanguage): ReactNode {
  return tokenizeLine(line, lang).map((token, index) =>
    token.className ? (
      <span key={index} className={token.className}>
        {token.text}
      </span>
    ) : (
      token.text
    )
  );
}
