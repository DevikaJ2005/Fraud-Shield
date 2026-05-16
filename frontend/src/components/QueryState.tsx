type QueryStateProps = {
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
};

export function QueryState({ title, message, actionLabel, onAction }: QueryStateProps) {
  return (
    <div className="rounded-md border border-line bg-white px-4 py-8 text-sm">
      <div className="font-medium text-ink">{title}</div>
      <div className="mt-1 text-slate-500">{message}</div>
      {actionLabel && onAction ? (
        <button className="mt-4 rounded-md border border-line px-3 py-2 text-sm hover:bg-panel" type="button" onClick={onAction}>
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}
