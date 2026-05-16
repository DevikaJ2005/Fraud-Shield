import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { GraphCanvas } from "../components/GraphCanvas";
import { QueryState } from "../components/QueryState";

export function FraudGraph() {
  const graph = useQuery({ queryKey: ["graph"], queryFn: api.graph, refetchInterval: 10_000 });

  return (
    <section>
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">Fraud Graph</h2>
        <p className="mt-1 text-sm text-slate-500">Rendering is capped at 500 nodes per PRD policy.</p>
      </header>
      <div className="rounded-md border border-line bg-white p-4">
        <div className="mb-3 flex items-center justify-between text-sm">
          <span>{graph.data?.nodes.length ?? 0} nodes</span>
          <span>{graph.data?.truncated ? "clustered view" : "full view"}</span>
        </div>
        {graph.isLoading ? <div className="grid min-h-[420px] place-items-center text-sm text-slate-500">Loading graph...</div> : null}
        {graph.isError ? <QueryState title="Graph unavailable" message="The backend did not return graph data." actionLabel="Retry" onAction={() => void graph.refetch()} /> : null}
        {!graph.isLoading && !graph.isError && graph.data && graph.data.nodes.length > 0 ? <GraphCanvas graph={graph.data} /> : null}
        {!graph.isLoading && !graph.isError && (!graph.data || graph.data.nodes.length === 0) ? <div className="grid min-h-[420px] place-items-center rounded border border-dashed border-line text-sm text-slate-500">No graph nodes returned.</div> : null}
      </div>
    </section>
  );
}
