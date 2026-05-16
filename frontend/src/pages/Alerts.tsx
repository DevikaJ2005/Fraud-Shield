import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { QueryState } from "../components/QueryState";

export function Alerts() {
  const alerts = useQuery({ queryKey: ["alerts"], queryFn: api.alerts, refetchInterval: 10_000 });

  return (
    <section>
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">Alerts</h2>
        <p className="mt-1 text-sm text-slate-500">Recent fraud alerts routed by severity policy.</p>
      </header>
      <div className="overflow-hidden rounded-md border border-line bg-white">
        {alerts.isLoading ? <div className="px-4 py-10 text-sm text-slate-500">Loading alerts...</div> : null}
        {alerts.isError ? <QueryState title="Alerts unavailable" message="The backend did not return alerts." actionLabel="Retry" onAction={() => void alerts.refetch()} /> : null}
        {!alerts.isLoading && !alerts.isError ? (
        <table className="w-full text-left text-sm">
          <thead className="border-b border-line bg-panel text-slate-600">
            <tr>
              <th className="px-4 py-3">Severity</th>
              <th className="px-4 py-3">Transaction</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {(alerts.data ?? []).map((alert) => (
              <tr key={alert.id} className="border-b border-line last:border-0">
                <td className="px-4 py-3">{alert.severity}</td>
                <td className="px-4 py-3">{alert.transaction_id}</td>
                <td className="px-4 py-3">{alert.created_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
        ) : null}
        {!alerts.isLoading && !alerts.isError && (alerts.data?.length ?? 0) === 0 ? <div className="px-4 py-10 text-sm text-slate-500">No alerts returned.</div> : null}
      </div>
    </section>
  );
}
