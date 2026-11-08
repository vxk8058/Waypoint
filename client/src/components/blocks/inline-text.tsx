import type { ReactNode } from "react";

/**
 * A tiny, safe subset of inline Markdown for AI-written text:
 *   **bold**   *italic* / _italic_   `code`   [label](https://link)
 * Everything else renders as plain text — no HTML is ever injected.
 */
const TOKEN = /(\*\*[^*]+?\*\*|`[^`]+?`|\[[^\]]+?\]\([^)\s]+?\)|\*[^*\s][^*]*?\*|\b_[^_\s][^_]*?_\b)/g;

export function InlineText({ text }: { text: string }) {
  const out: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const m of text.matchAll(TOKEN)) {
    const tok = m[0];
    const at = m.index ?? 0;
    if (at > last) out.push(text.slice(last, at));
    last = at + tok.length;

    if (tok.startsWith("**")) {
      out.push(
        <strong key={key++} className="font-semibold text-blue-grey-050">
          {tok.slice(2, -2)}
        </strong>,
      );
    } else if (tok.startsWith("`")) {
      out.push(
        <code key={key++} className="rounded bg-surface-raised px-1 py-0.5 font-mono text-[0.9em] text-blue-grey-100">
          {tok.slice(1, -1)}
        </code>,
      );
    } else if (tok.startsWith("[")) {
      const close = tok.indexOf("](");
      const label = tok.slice(1, close);
      const href = tok.slice(close + 2, -1);
      out.push(
        isSafeHref(href) ? (
          <a
            key={key++}
            href={href}
            target={href.startsWith("/") ? undefined : "_blank"}
            rel="noreferrer noopener"
            className="text-purple-300 underline decoration-purple-300/40 underline-offset-2 hover:decoration-purple-300"
          >
            {label}
          </a>
        ) : (
          label
        ),
      );
    } else {
      out.push(<em key={key++}>{tok.slice(1, -1)}</em>);
    }
  }
  if (last < text.length) out.push(text.slice(last));
  return <>{out}</>;
}

/** Only http(s), mailto and same-site paths; never javascript: or data:. */
function isSafeHref(href: string) {
  return /^(https?:\/\/|mailto:|\/(?!\/))/i.test(href);
}
