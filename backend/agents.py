"""Agent roster, role prompts and routing helpers.

The demo has three build roles:

    Mike (team leader) -> Bob (architect) -> Alex (engineer)

Only Alex may write files; Bob may plan; Mike may only read project state.
Hand-off is uniform: an agent ends its final message with ``@Bob`` / ``@Alex``
on the last line, and the orchestrator enqueues that agent next.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

AGENT_ORDER = ("mike", "bob", "alex")

AGENT_NAMES = {"mike": "Mike", "bob": "Bob", "alex": "Alex"}


@dataclass(frozen=True)
class AgentSpec:
    key: str
    name: str
    role: str
    system: str
    skills: tuple[str, ...]
    tools: frozenset[str]


@dataclass(frozen=True)
class Segment:
    """One task chunk addressed to one or more agents by @mention."""

    agents: tuple[str, ...]
    text: str


MIKE_SYSTEM = """你是 Mike，团队领导。你不写代码。
根据用户请求和项目上下文，输出：
1. 需求理解（1-2 句）
2. 任务拆解（1-3 条）
3. 最后一行只能是 @Bob 或 @Alex，不能同时 @ 两人，也不要在正文中间 @ 人。

判断规则：
- 需要架构设计：全栈/后端、多表、登录/支付/订单/库存、复杂状态、多个页面、需要数据模型或 API 设计、续改已有后端 → @Bob
- 简单前端、样式/文案调整、小修复、单页小工具 → @Alex

只输出中文，不要 markdown 代码围栏。最终答复的最后一行必须是 @Bob 或 @Alex。"""

MIKE_CONSULT_SYSTEM = """你是 Mike，团队领导，从产品目标、整体交付和协作角度回答。
不要修改代码，不要分配任务，不要输出 @名字。基于项目上下文简洁直接地回答。
如果问题涉及天气、新闻、股价等实时外部数据，而上下文没有这些数据，明确说明无法获取实时数据，不要编造。"""

BOB_CONSULT_SYSTEM = """你是 Bob，架构师，从系统架构、数据模型、API 和技术选型角度回答。
不要修改代码，不要输出 @名字。基于项目上下文回答，尽量引用真实的文件名、表名和接口名。
上下文没有的信息要明确说明，不要编造；不要编造实时数据。"""

ALEX_CONSULT_SYSTEM = """你是 Alex，工程师，从实现、文件结构、构建和运行状态角度回答。
不要修改代码，不要输出 @名字。基于项目上下文回答，尽量引用真实的文件名和路径。
上下文没有的信息要明确说明，不要编造；不要编造实时数据。"""

TITLE_SYSTEM = """你是项目命名助手。根据用户的第一条需求，给出一个简短、具体的项目名称。
规则：
- 只输出名称本身，不要解释、不要引号/书名号/句末标点、不要 markdown
- 6-16 个汉字（英文需求则 2-5 个单词），最多 24 个字符
- 概括核心产品形态和功能，例如「团队任务看板」「旅行行程规划器」
- 使用与需求相同的语言
- 不要输出「未命名项目」「新项目」这类空泛名称"""

AGENTS: dict[str, AgentSpec] = {
    "mike": AgentSpec(
        key="mike",
        name="Mike",
        role="团队领导",
        system=MIKE_SYSTEM,
        skills=("intake", "routing", "summary"),
        tools=frozenset({"read_project_state"}),
    ),
    "bob": AgentSpec(
        key="bob",
        name="Bob",
        role="架构师",
        system="",  # Bob's build prompt is the structured Planner prompt in agent.py.
        skills=("architecture", "schema", "api-design"),
        tools=frozenset({"read_project_state", "validate_plan"}),
    ),
    "alex": AgentSpec(
        key="alex",
        name="Alex",
        role="工程师",
        system="",  # Alex uses the Coder/Styles/Backend prompts in agent.py.
        skills=("codegen", "review", "build", "deploy"),
        tools=frozenset(
            {
                "read_project_state",
                "read_file",
                "write_file",
                "publish_files",
                "build_preview",
                "start_runtime",
                "check_health",
            }
        ),
    ),
}

CONSULT_SYSTEMS = {
    "mike": MIKE_CONSULT_SYSTEM,
    "bob": BOB_CONSULT_SYSTEM,
    "alex": ALEX_CONSULT_SYSTEM,
}

_MENTION_RE = re.compile(r"(?<![A-Za-z0-9])@(mike|bob|alex)(?![A-Za-z0-9])", re.IGNORECASE)

# Leading request filler ("帮我做一个…") that carries no naming information.
_TITLE_FILLER_RE = re.compile(
    r"^(?:(?:请|麻烦|帮我|帮忙|我想|我要|我们想|我们需要|需要|想要)+)?"
    r"(?:帮我|帮忙)?"
    r"(?:做|写|开发|创建|搭建|实现|设计|生成|构建|制作)?"
    r"(?:一个|一款|一套|个)?"
)
_TITLE_TRIM = " \t，,、;；:：-—·\"'“”‘’《》「」『』【】[]()（）"
_GENERIC_TITLES = {"未命名项目", "新项目", "项目", "应用", "我的项目"}


def fallback_title(prompt: str | None, limit: int = 24) -> str:
    """Deterministic project name used before/without an LLM.

    Takes the first sentence, drops request filler, and prefers a clause
    boundary rather than cutting a long sentence in the middle.
    """
    text = _MENTION_RE.sub("", prompt or "")
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        return "未命名项目"
    text = re.split(r"[。！？!?\n]", text, maxsplit=1)[0].strip()
    text = re.sub(r"\s+", " ", text)
    text = _TITLE_FILLER_RE.sub("", text).strip(_TITLE_TRIM)
    if not text:
        return "未命名项目"
    if len(text) > limit:
        head = text[:limit]
        cut = max(head.rfind(ch) for ch in "，,、;；:：")
        text = (head[:cut] if cut >= 6 else head).strip(_TITLE_TRIM)
    return text[:limit] or "未命名项目"


def sanitize_title(raw: str | None, fallback: str) -> str:
    """Keep only the first clean line of an LLM title response."""
    text = re.sub(r"```[A-Za-z0-9_-]*", "", raw or "")
    line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    line = re.sub(r"^.{0,8}?(?:项目名称|名称|标题|名字)\s*[:：]\s*", "", line)
    line = line.strip(" \t`*#\"'“”‘’《》「」『』【】[]()（）")
    line = line.strip("。．.!！?？,，;；:：、")
    line = re.sub(r"\s+", " ", line).strip()
    if len(line) < 2 or line in _GENERIC_TITLES:
        return fallback
    return line[:24]

# Imperative build actions. These win over consult markers, so "介绍项目并加一个
# 搜索框" is still a build request.
STRONG_BUILD_PATTERNS = (
    "做一个",
    "做个",
    "帮我做个",
    "帮我做一个",
    "帮我写个",
    "帮我写一个",
    "帮我写页面",
    "帮我写代码",
    "写一个",
    "创建一个",
    "加一个",
    "加上",
    "添加",
    "改成",
    "改一下",
    "修改",
    "删除",
    "删掉",
    "去掉",
    "修复",
    "修一下",
    "重构",
    "优化一下",
    "部署一下",
    "上线",
    "搭建",
    "生成一个",
    "开发一个",
    "实现一个",
    "实现一下",
    "实现该",
    "实现这个",
    "我需要一个",
    "我想要一个",
    "需要一个",
    "想要一个",
)

# Generic verbs. They only mean "build" when the message is not asking a
# consult question: "代码实现" in an introduction request must not trigger a build.
WEAK_BUILD_PATTERNS = (
    "实现",
    "生成",
    "创建",
    "开发",
    "增加",
    "优化",
)

CONSULT_PATTERNS = (
    "?",
    "？",
    "怎么",
    "如何",
    "为什么",
    "是什么",
    "什么",
    "介绍",
    "说明",
    "总结",
    "分析",
    "解释",
    "讲解",
    "描述",
    "对比",
    "评估",
    "看看",
    "看一下",
    "评价",
    "建议",
    "多少",
    "哪些",
    "是否",
    "天气",
    "新闻",
    "怎么样",
    "能不能",
    "可以吗",
    "吗",
)

GREETINGS = ("你好", "您好", "hi", "hello", "你是谁", "你能做什么")


def normalize_agent(value: str | None) -> str:
    if value in AGENTS:
        return value  # type: ignore[return-value]
    lowered = (value or "").lower()
    for key, name in AGENT_NAMES.items():
        if lowered == name.lower():
            return key
    return "mike"


def parse_mentions(text: str | None, *, tail_only: bool = False) -> list[str]:
    """Return mentioned agent keys in order, de-duplicated.

    ``tail_only`` is used for agent-to-agent hand-off: only the last non-empty
    line is scanned, so an @ mention inside the body never triggers a hand-off.
    """
    if not text:
        return []
    scan = text
    if tail_only:
        lines = [line for line in text.strip().splitlines() if line.strip()]
        scan = lines[-1] if lines else ""
    found: list[str] = []
    for match in _MENTION_RE.finditer(scan):
        key = match.group(1).lower()
        if key not in found:
            found.append(key)
    return found


SEPARATORS = " \t\r\n,，。.;；:：、"

BROADCAST_MARKERS = (
    "你们",
    "大家",
    "两位",
    "两个人",
    "2个人",
    "俩人",
    "你俩",
    "你们俩",
    "所有人",
    "团队",
    "全体",
    "分别",
    "各自",
    "每个人",
    "每位",
)

CONNECTIVE_PREFIXES = ("请", "麻烦", "帮我", "帮忙", "请问", "我想问", "想问", "以下是")

QUESTION_PREFIX_MARKERS = (
    "?",
    "？",
    "怎么",
    "如何",
    "为什么",
    "是什么",
    "什么",
    "介绍",
    "说明",
    "总结",
    "分析",
    "解释",
    "看看",
    "评价",
    "多少",
    "哪些",
    "是否",
    "天气",
    "新闻",
    "怎么样",
)

_SENTENCE_RE = re.compile(r"[^。！？!?\n]+[。！？!?]?|\n+")


def _prefix_is_connective(prefix: str) -> bool:
    cleaned = prefix.strip(SEPARATORS)
    if len(cleaned) <= 3:
        return True
    return any(
        cleaned == item
        or cleaned.startswith(item + " ")
        or cleaned.startswith(item + "，")
        for item in CONNECTIVE_PREFIXES
    )


def _prefix_is_question(prefix: str) -> bool:
    return any(marker in prefix for marker in QUESTION_PREFIX_MARKERS)


def _chunk_pieces(
    chunk: str,
    agents: tuple[str, ...],
    all_agents: tuple[str, ...],
) -> list[tuple[tuple[str, ...], str]]:
    """Split one @chunk into ordered pieces.

    Broadcast sentences (``你们/大家/两位/分别/各自``) are addressed to every
    mentioned agent; other sentences stay with the current @mention.
    """
    pieces: list[tuple[tuple[str, ...], str]] = []
    buffer: list[str] = []
    buffer_shared = False

    for sentence in _SENTENCE_RE.findall(chunk):
        text = sentence.strip()
        if not text:
            continue
        shared = any(marker in text for marker in BROADCAST_MARKERS)
        if buffer and shared != buffer_shared:
            pieces.append(
                (all_agents if buffer_shared else agents, "\n".join(buffer))
            )
            buffer = []
        buffer.append(text)
        buffer_shared = shared

    if buffer:
        pieces.append((all_agents if buffer_shared else agents, "\n".join(buffer)))
    return pieces


def split_segments(message: str) -> list[Segment]:
    """Split a user message into per-agent task chunks.

    Rules:
    - Text after ``@Alex`` belongs to Alex until the next @mention.
    - Consecutive mentions share the following text: ``@Bob @Alex 做一个页面``.
    - An un-addressed question before the first mention goes to Mike (the
      default/team leader). Short connectives such as ``请`` are attached to
      the first mentioned agent instead.
    - Sentences containing ``你们/大家/两位/分别/各自`` are shared by every
      mentioned agent, e.g. ``你们2个人介绍下当前项目``.
    """
    text = message or ""
    matches = list(_MENTION_RE.finditer(text))
    if not matches:
        return [Segment(("mike",), text.strip())]

    mentioned = dedupe(match.group(1).lower() for match in matches)
    all_agents = tuple(mentioned)
    segments: list[Segment] = []

    prefix = text[: matches[0].start()].strip(SEPARATORS)
    attach_prefix = bool(prefix)
    if prefix and _prefix_is_question(prefix) and not _prefix_is_connective(prefix):
        segments.append(Segment(("mike",), prefix))
        attach_prefix = False

    agents: list[str] = []
    for index, match in enumerate(matches):
        key = match.group(1).lower()
        if key not in agents:
            agents.append(key)

        text_start = match.end()
        text_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[text_start:text_end]

        if index + 1 < len(matches) and not chunk.strip(SEPARATORS):
            # "@Bob @Alex ..." — both agents share the following text.
            continue

        for piece_agents, piece_text in _chunk_pieces(
            chunk, tuple(agents), all_agents
        ):
            if not piece_text:
                continue
            if attach_prefix and prefix:
                piece_text = f"{prefix} {piece_text}".strip()
                attach_prefix = False
            segments.append(Segment(piece_agents, piece_text))
        agents = []

    if not segments:
        return [Segment(tuple(mentioned), "请按你的角色回答。")]
    return segments


def classify_intent(message: str, *, has_project: bool) -> str:
    text = (message or "").lower()
    if any(pattern in text for pattern in STRONG_BUILD_PATTERNS):
        return "build"
    if any(pattern in text for pattern in CONSULT_PATTERNS):
        return "consult"
    if any(pattern in text for pattern in WEAK_BUILD_PATTERNS):
        return "build"
    if not has_project:
        if any(greeting in text for greeting in GREETINGS):
            return "consult"
        return "build"
    return "consult"


def dedupe(keys: Iterable[str]) -> list[str]:
    result: list[str] = []
    for key in keys:
        if key in AGENTS and key not in result:
            result.append(key)
    return result


def dependency_order(keys: Iterable[str]) -> list[str]:
    present = set(dedupe(keys))
    return [key for key in AGENT_ORDER if key in present]


def initial_targets(message: str, intent: str) -> list[str]:
    mentioned = parse_mentions(message)
    if intent == "build":
        if mentioned:
            return dependency_order(mentioned)
        return ["mike"]
    if mentioned:
        return dedupe(mentioned)
    return ["mike"]


def merge_targets(
    pending: Iterable[str], new_targets: Iterable[str], *, current: str, intent: str
) -> list[str]:
    combined = list(pending)
    for key in new_targets:
        if key == current or key in combined:
            continue
        combined.append(key)
    if intent == "build":
        return dependency_order(combined)
    return dedupe(combined)
