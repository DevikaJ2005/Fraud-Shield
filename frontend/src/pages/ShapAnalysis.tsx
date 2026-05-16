import { useMutation } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api, type PredictionRequest } from "../api/client";

function demoPayload(): PredictionRequest {
  const id = Date.now();
  return {
    transaction_id: `demo-${id}`,
    account_id: `acct-${id % 5}`,
    merchant_id: "merchant-demo",
    device_id: id % 2 === 0 ? "shared-device-demo" : `device-${id}`,
    ip_address: id % 3 === 0 ? "10.10.10.10" : `10.10.10.${(id % 200) + 20}`,
    amount: id % 2 === 0 ? 9800 : 420,
    timestamp: new Date().toISOString(),
    is_mobile: true
  };
}

export function ShapAnalysis() {
  const prediction = useMutation({ mutationFn: api.predict });
  const data = (prediction.data?.shap_explanation ?? []).map((item) => ({
    feature: item.feature,
    value: item.shap_value
  }));

  return (
    <section>
      <header className="mb-6">
        <h2 className="text-2xl font-semibold">SHAP Analysis</h2>
        <p className="mt-1 text-sm text-slate-500">Feature attribution panels use SHAP as the explanation source of truth.</p>
      </header>
      <button className="mb-4 rounded-md bg-ink px-4 py-2 text-sm font-medium text-white" type="button" onClick={() => prediction.mutate(demoPayload())}>
        {prediction.isPending ? "Scoring..." : "Score Demo Transaction"}
      </button>
      {prediction.isError ? <p className="mb-4 text-sm text-risk">Prediction failed. Check that the backend is running and the model is available.</p> : null}
      {prediction.data ? <p className="mb-4 text-sm text-slate-600">{prediction.data.narration}</p> : null}
      <div className="h-[420px] rounded-md border border-line bg-white p-4">
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} layout="vertical" margin={{ left: 24 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis type="number" />
              <YAxis dataKey="feature" type="category" width={140} />
              <Tooltip />
              <Bar dataKey="value" fill="#0f766e" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="grid h-full place-items-center text-sm text-slate-500">Run a demo transaction to view real SHAP values.</div>
        )}
      </div>
    </section>
  );
}
