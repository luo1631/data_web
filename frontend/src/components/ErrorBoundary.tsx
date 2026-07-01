import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="h-full flex items-center justify-center p-8">
          <div className="rounded-[var(--radius-md)] border border-red-400 bg-red-50 dark:bg-red-900/20 p-6 max-w-lg text-sm space-y-3">
            <h2 className="font-bold text-red-600 dark:text-red-400 text-lg">Render Error</h2>
            <pre className="text-xs text-red-700 dark:text-red-300 whitespace-pre-wrap break-all">
              {this.state.error.message}
            </pre>
            <details className="text-[11px] text-red-600 dark:text-red-400">
              <summary>Stack</summary>
              <pre className="mt-1 whitespace-pre-wrap break-all">{this.state.error.stack}</pre>
            </details>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="rounded-[var(--radius-sm)] bg-red-600 text-white px-3 py-1.5 text-xs font-medium hover:opacity-90"
            >
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
