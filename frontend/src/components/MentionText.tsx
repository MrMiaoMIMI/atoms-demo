const MENTION_RE = /((?<![A-Za-z0-9])@(?:Mike|Bob|Alex)(?![A-Za-z0-9]))/gi;
const IS_MENTION = /^(?<![A-Za-z0-9])@(?:Mike|Bob|Alex)(?![A-Za-z0-9])$/i;

export default function MentionText({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  const parts = text.split(MENTION_RE);
  return (
    <span className={className}>
      {parts.map((part, index) =>
        IS_MENTION.test(part) ? (
          <span
            key={`${part}-${index}`}
            className="mx-0.5 inline-flex items-center rounded-[6px] bg-brand-50 px-1.5 py-0.5 text-[13px] font-medium leading-[18px] text-brand-text"
          >
            {part}
          </span>
        ) : (
          part
        )
      )}
    </span>
  );
}
