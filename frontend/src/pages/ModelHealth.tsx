import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { Metric } from "../components/Metric";
import { QueryState } from "../components/QueryState";

export function ModelHealth() {
  const model = useQuery({ queryKey: ["model-status"], queryFn: api.modelStatus, refetchInterval: 10_000 });

  return (
    <section>
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">Model Health</h2>
        <p className="mt-1 text-sm text-slate-500">Active model, schema, retraining, and drift status.</p>
      </header>
      <div className="grid gap-4 sm:grid-cols-3">
        <Metric label="Availability" value={model.data?.status ?? "checking"} />
        <Metric label="Version" value={model.data?.model_version ?? "-"} />
        <Metric label="Schema" value={model.data?.feature_schema_version ?? "-"} />
      </div>
      {model.isError ? <div className="mt-4"><QueryState title="Model status unavailable" message="The backend did not return model health." actionLabel="Retry" onAction={() => void model.refetch()} /></div> : null}
      <div className="mt-6 rounded-md border border-line bg-white px-4 py-10 text-sm text-slate-500">
        Retraining history will populate from Supabase model_registry.
      </div>
    </section>
  );
}
