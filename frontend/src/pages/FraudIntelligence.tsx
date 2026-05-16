import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { QueryState } from "../components/QueryState";

export function FraudIntelligence() {
  const feed = useQuery({ queryKey: ["fraud-intelligence"], queryFn: api.intelligence, refetchInterval: 60_000 });

  return (
    <section>
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">Fraud Intelligence Feed</h2>
        <p className="mt-1 text-sm text-slate-500">Structured fraud patterns sourced by n8n workflows.</p>
      </header>
      <div className="grid gap-3">
        {feed.isLoading ? <div className="rounded-md border border-line bg-white px-4 py-10 text-sm text-slate-500">Loading intelligence feed...</div> : null}
        {feed.isError ? <QueryState title="Intelligence feed unavailable" message="The backend did not return fraud intelligence." actionLabel="Retry" onAction={() => void feed.refetch()} /> : null}
        {(feed.data ?? []).map((item) => (
          <article key={item.title} className="rounded-md border border-line bg-white p-4">
            <h3 className="font-medium">{item.title}</h3>
            <p className="mt-2 text-sm text-slate-600">{item.summary}</p>
          </article>
        ))}
        {!feed.isLoading && !feed.isError && (feed.data?.length ?? 0) === 0 ? <div className="rounded-md border border-line bg-white px-4 py-10 text-sm text-slate-500">No intelligence items returned.</div> : null}
      </div>
    </section>
  );
}
