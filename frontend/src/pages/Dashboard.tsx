import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Square } from "lucide-react";
import { api } from "../api/client";
import { Metric } from "../components/Metric";
import { QueryState } from "../components/QueryState";

export function Dashboard() {
  const queryClient = useQueryClient();
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 10_000 });
  const model = useQuery({ queryKey: ["model-status"], queryFn: api.modelStatus, refetchInterval: 10_000 });
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: api.alerts, refetchInterval: 10_000 });
  const transactions = useQuery({ queryKey: ["transactions"], queryFn: api.transactions, refetchInterval: 5_000 });
  const simulator = useQuery({ queryKey: ["simulator-status"], queryFn: api.simulatorStatus, refetchInterval: 5_000 });
  const refreshSimulator = () => void queryClient.invalidateQueries({ queryKey: ["simulator-status"] });
  const startSimulator = useMutation({ mutationFn: api.startSimulator, onSuccess: refreshSimulator });
  const stopSimulator = useMutation({ mutationFn: api.stopSimulator, onSuccess: refreshSimulator });

  return (
    <section>
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="mt-1 text-sm text-slate-500">Polling-based operational view for fraud scoring and alerts.</p>
      </header>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="Backend status" value={health.data?.status ?? "checking"} tone={health.data?.status === "ok" ? "safe" : "risk"} />
        <Metric label="Model status" value={model.data?.status ?? "checking"} tone={model.data?.status === "available" ? "safe" : "risk"} />
        <Metric label="Simulator" value={simulator.data?.running ? "live" : "stopped"} tone={simulator.data?.running ? "safe" : "risk"} />
        <Metric label="Recent alerts" value={String(alerts.data?.length ?? 0)} tone={(alerts.data?.length ?? 0) > 0 ? "risk" : "safe"} />
      </div>
      <div className="mt-6 grid gap-4 lg:grid-cols-[1fr_auto] lg:items-center">
        <div className="rounded-md border border-line bg-white px-4 py-3">
          <div className="grid gap-3 text-sm sm:grid-cols-4">
            <div>
              <div className="text-slate-500">Generated</div>
              <div className="font-semibold">{simulator.data?.generated_count ?? 0}</div>
            </div>
            <div>
              <div className="text-slate-500">Fraud-like</div>
              <div className="font-semibold">{simulator.data?.fraud_count ?? 0}</div>
            </div>
            <div>
              <div className="text-slate-500">Scenario</div>
              <div className="font-semibold">{simulator.data?.last_scenario ?? "-"}</div>
            </div>
            <div>
              <div className="text-slate-500">Failures</div>
              <div className="font-semibold">{simulator.data?.failed_count ?? 0}</div>
            </div>
          </div>
          {simulator.data?.last_error ? <p className="mt-3 text-sm text-risk">{simulator.data.last_error}</p> : null}
        </div>
        <div className="flex gap-2">
          <button
            className="inline-flex items-center gap-2 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
            type="button"
            disabled={startSimulator.isPending || simulator.data?.running}
            onClick={() => startSimulator.mutate()}
          >
            <Play size={16} />
            Start
          </button>
          <button
            className="inline-flex items-center gap-2 rounded-md border border-line px-4 py-2 text-sm font-medium disabled:opacity-50"
            type="button"
            disabled={stopSimulator.isPending || !simulator.data?.running}
            onClick={() => stopSimulator.mutate()}
          >
            <Square size={16} />
            Stop
          </button>
        </div>
      </div>
      <div className="mt-6 overflow-hidden rounded-md border border-line bg-white">
        <div className="border-b border-line px-4 py-3 font-medium">Live Transaction Feed</div>
        {transactions.isLoading ? <div className="px-4 py-10 text-sm text-slate-500">Loading transactions...</div> : null}
        {transactions.isError ? <QueryState title="Transactions unavailable" message="The backend did not return the transaction feed." actionLabel="Retry" onAction={() => void transactions.refetch()} /> : null}
        {!transactions.isLoading && !transactions.isError ? (
          <>
            <table className="w-full text-left text-sm">
              <thead className="bg-panel text-slate-600">
                <tr>
                  <th className="px-4 py-3">Transaction</th>
                  <th className="px-4 py-3">Account</th>
                  <th className="px-4 py-3">Merchant</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3">Score</th>
                  <th className="px-4 py-3">Severity</th>
                </tr>
              </thead>
              <tbody>
                {(transactions.data ?? []).map((item) => (
                  <tr key={item.transaction_id} className="border-t border-line">
                    <td className="px-4 py-3">{item.transaction_id}</td>
                    <td className="px-4 py-3">{item.account_id}</td>
                    <td className="px-4 py-3">{item.merchant_id}</td>
                    <td className="px-4 py-3">{item.amount.toFixed(2)}</td>
                    <td className="px-4 py-3">{item.fraud_probability?.toFixed(3) ?? "-"}</td>
                    <td className="px-4 py-3">{item.severity ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {(transactions.data?.length ?? 0) === 0 ? <div className="px-4 py-10 text-sm text-slate-500">No transactions returned.</div> : null}
          </>
        ) : null}
      </div>
    </section>
  );
}
