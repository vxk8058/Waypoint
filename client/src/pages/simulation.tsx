import { useEffect, useRef, useState, type SubmitEvent, type KeyboardEvent, type SVGProps } from "react";
import { AiDocument } from "../components/ai-document";
import { Button } from "../components/button";
import { Text } from "../components/text";
import { apiFetch } from "../lib/api";
import { simulationSuggestions } from "./simulation-sample";

function Icon(props: SVGProps<SVGSVGElement>) {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props} />;
}

function ArrowUpIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon strokeWidth={2} {...props}>
      <path d="M12 19V5M6 11l6-6 6 6" />
    </Icon>
  );
}

function SparkleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <Icon {...props}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6.3 6.3l2.5 2.5M15.2 15.2l2.5 2.5M6.3 17.7l2.5-2.5M15.2 8.8l2.5-2.5" />
    </Icon>
  );
}

// shortcut: timed steps, not live agent events; stream the agent's node path if exact progress is needed.
const STEPS = ["Reading your accounts", "Checking what your question needs", "Running the numbers", "Designing your answer"];

function ProgressSteps() {
  const [step, setStep] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setStep((s) => Math.min(s + 1, STEPS.length - 1)), 12000);
    return () => clearInterval(timer);
  }, []);
  return (
    <ol aria-label="Progress" className="flex flex-col gap-1 text-sm">
      {STEPS.map((label, i) => (
        <li
          key={label}
          aria-current={i === step ? "step" : undefined}
          className={i < step ? "text-blue-grey-400" : i === step ? "animate-pulse text-blue-grey-050" : "text-blue-grey-600"}
        >
          {i < step ? "✓" : i === step ? "●" : "○"} {label}
          {i === step && "…"}
        </li>
      ))}
    </ol>
  );
}

type Result = { status: "idle" } | { status: "loading"; prompt: string } | { status: "done"; prompt: string; document: unknown } | { status: "error"; message: string };

export function Simulation() {
  const [prompt, setPrompt] = useState("");
  const [result, setResult] = useState<Result>({ status: "idle" });
  const resultsRef = useRef<HTMLDivElement>(null);

  const loading = result.status === "loading";

  async function run(text: string) {
    const value = text.trim();
    if (!value || loading) return;
    setPrompt(value);
    setResult({ status: "loading", prompt: value });
    resultsRef.current?.scrollTo({ top: 0 });
    try {
      const document = await apiFetch<unknown>("/api/me/agent", { method: "POST", body: { question: value } });
      setResult({ status: "done", prompt: value, document });
    } catch (err) {
      setResult({ status: "error", message: err instanceof Error ? err.message : "Couldn't generate an answer. Please try again." });
    }
  }

  function handleSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    run(prompt);
  }

  // Enter sends, Shift+Enter adds a new line.
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      run(prompt);
    }
  }

  return (
    <div className="flex flex-col gap-10">
      <Text variant="h2" as="h1">
        Simulation
      </Text>

      <section
        aria-label="Goal simulation"
        className="grid overflow-hidden rounded-lg border border-blue-grey-700 md:h-[calc(100vh-15rem)] md:min-h-[34rem] md:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]"
      >
        {/* Left: prompt */}
        <div className="@container flex flex-col gap-6 border-b border-blue-grey-700 p-5 md:border-r md:border-b-0">
          <div className="flex flex-col gap-2">
            {/* Scales with the panel width (capped at the h3 size) so it always fits on one line. */}
            <Text variant="h3" as="h2" className="whitespace-nowrap" style={{ fontSize: "clamp(1rem, 4.6cqi, 1.5rem)" }}>
              How can I help you reach your goal?
            </Text>
          </div>

          <form
            onSubmit={handleSubmit}
            className="flex flex-col gap-2 rounded-lg border border-blue-grey-600 bg-canvas p-3 transition-colors focus-within:border-purple-400 focus-within:ring-2 focus-within:ring-purple-400/40 hover:border-blue-grey-500"
          >
            <label htmlFor="simulation-prompt" className="sr-only">
              Your question
            </label>
            <textarea
              id="simulation-prompt"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              rows={4}
              placeholder="e.g. Can I buy a car by Christmas if I stop eating out?"
              className="min-h-24 w-full resize-none bg-transparent text-base text-blue-grey-050 outline-none placeholder:text-blue-grey-500"
            />
            <div className="flex items-center justify-between gap-2">
              <Text variant="caption">Shift + Enter for a new line</Text>
              <Button type="submit" size="sm" disabled={!prompt.trim() || loading}>
                {loading ? "Simulating…" : "Simulate"}
                {!loading && <ArrowUpIcon className="size-4" />}
              </Button>
            </div>
          </form>

          <div className="mt-auto pt-10">
            <ul aria-label="Suggestions" className="flex flex-col gap-1.5">
              {simulationSuggestions.map((s) => (
                <li key={s}>
                  <button
                    type="button"
                    onClick={() => run(s)}
                    disabled={loading}
                    className="w-full cursor-pointer rounded-lg border border-blue-grey-700 px-3 py-2 text-left text-sm text-blue-grey-200 transition-colors hover:bg-surface hover:text-blue-grey-050 focus-visible:ring-2 focus-visible:ring-purple-400/60 focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50"
                  >
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </div>

        {/* Right: result */}
        <div ref={resultsRef} aria-live="polite" aria-busy={loading} className="min-h-[24rem] overflow-y-auto p-5">
          {result.status === "idle" && (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
              <span className="grid size-12 place-items-center rounded-full border-2 border-blue-grey-700 text-blue-grey-500">
                <SparkleIcon className="size-6" />
              </span>
              <Text variant="body" weight="medium">
                Your simulation will appear here
              </Text>
              <Text variant="small" tone="muted" className="max-w-xs">
                Ask a question or pick a suggestion to see projections, charts and a plan.
              </Text>
            </div>
          )}

          {result.status === "loading" && (
            <div className="flex flex-col gap-4" aria-label="Generating simulation">
              <Text variant="small" tone="muted" className="animate-pulse">
                Simulating “{result.prompt}”…
              </Text>
              <ProgressSteps />
              <Text variant="caption">This usually takes about a minute.</Text>
              <span className="h-7 w-2/3 animate-pulse rounded bg-surface-raised" />
              <span className="h-4 w-full animate-pulse rounded bg-surface-raised" />
              <span className="h-4 w-5/6 animate-pulse rounded bg-surface-raised" />
              <div className="grid grid-cols-3 gap-3">
                {[0, 1, 2].map((i) => (
                  <span key={i} className="h-20 animate-pulse rounded-lg bg-surface-raised" />
                ))}
              </div>
              <span className="h-56 w-full animate-pulse rounded-lg bg-surface-raised" />
            </div>
          )}

          {result.status === "error" && (
            <p role="alert" className="rounded-lg border border-red-vivid-700 bg-red-vivid-900/30 px-3 py-2 text-sm text-red-vivid-200">
              {result.message}
            </p>
          )}
          {result.status === "done" && <AiDocument document={result.document} />}
        </div>
      </section>
    </div>
  );
}

export default Simulation;
