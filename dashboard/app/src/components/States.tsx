import './States.css';

export function Loading({ title }: { title: string }) {
  return (
    <div className="state" role="status">
      <div className="page">
        <p className="state__title">{title}</p>
        <p className="state__figure" aria-hidden="true">
          ···
        </p>
        <p className="state__text">Loading contributions…</p>
      </div>
    </div>
  );
}

export function LoadError({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) {
  return (
    <div className="state" role="alert">
      <div className="page">
        <p className="state__title">{title}</p>
        <h1 className="state__heading">The data could not be loaded</h1>
        <p className="state__text">{message}</p>
        <p className="state__text">
          If you host this dashboard yourself, run <code>generate_report.py</code> and build again so{' '}
          <code>activity.json</code> is published next to the page.
        </p>
        <button type="button" className="state__action" onClick={onRetry}>
          Try again
        </button>
      </div>
    </div>
  );
}

export function NoData({ title }: { title: string }) {
  return (
    <div className="state">
      <div className="page">
        <p className="state__title">{title}</p>
        <h1 className="state__heading">No activity yet</h1>
        <p className="state__text">
          The report has no pull requests or issues. Add users and repositories to <code>input/github.json</code>, then run
          the report again.
        </p>
      </div>
    </div>
  );
}
