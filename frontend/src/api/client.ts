const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "https://fraud-shield-production-991d.up.railway.app";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers
    }
  });

  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export type ModelStatus = {
  model_version: string;
  feature_schema_version: string;
  status: string;
};

export type GraphPayload = {
  nodes: Array<{ id: string; type: string }>;
  links: Array<{ source: string; target: string; type: string }>;
  truncated: boolean;
};

export type Alert = {
  id: string | number;
  severity: "LOW" | "MEDIUM" | "HIGH";
  transaction_id: string;
  created_at: string;
};

export type TransactionSummary = {
  transaction_id: string;
  account_id: string;
  merchant_id: string;
  amount: number;
  occurred_at: string;
  fraud_probability: number | null;
  confidence: number | null;
  severity: "LOW" | "MEDIUM" | "HIGH" | null;
  model_version: string;
  feature_schema_version: string;
};

export type PredictionRequest = {
  transaction_id: string;
  account_id: string;
  merchant_id: string;
  device_id: string;
  ip_address: string;
  amount: number;
  timestamp: string;
  is_mobile: boolean;
};

export type PredictionResponse = {
  transaction_id: string;
  fraud_probability: number;
  confidence: number;
  severity: "LOW" | "MEDIUM" | "HIGH" | null;
  model_version: string;
  feature_schema_version: string;
  patterns: Array<{ name: string; value: boolean; evidence: string }>;
  graph: {
    graph_degree: number;
    clustering_coefficient: number;
    ring_detected: boolean;
    shared_device_detected: boolean;
    shared_ip_detected: boolean;
    suspicious_cluster_detected: boolean;
    shared_entities: string[];
    risk_propagation_score: number;
  };
  shap_explanation: Array<{ feature: string; value: number | boolean; shap_value: number; direction: string }>;
  narration: string;
};

export const api = {
  modelStatus: () => request<ModelStatus>("/api/v1/model/status"),
  graph: () => request<GraphPayload>("/api/v1/graph/current"),
  alerts: () => request<Alert[]>("/api/v1/alerts"),
  transactions: () => request<TransactionSummary[]>("/api/v1/transactions"),
  intelligence: () => request<Array<{ title: string; summary: string }>>("/api/v1/fraud-intelligence"),
  predict: (payload: PredictionRequest) =>
    request<PredictionResponse>("/api/v1/predict", {
      method: "POST",
      body: JSON.stringify(payload)
    })
};
