import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";

interface Props {
  type: string;
  children: ReactNode;
}

/** One malformed block never takes down the rest of the AI response. */
export class BlockBoundary extends Component<Props, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    if (import.meta.env.DEV) console.error(`[AiComponent] "${this.props.type}" block crashed`, error, info.componentStack);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="rounded-xl border border-dashed border-blue-grey-800 p-4 text-sm text-blue-grey-500">
        This part of the response couldn’t be displayed.
      </div>
    );
  }
}
