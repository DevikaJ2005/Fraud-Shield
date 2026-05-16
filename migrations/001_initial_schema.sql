create table if not exists transactions (
  id bigserial primary key,
  transaction_id text unique not null,
  account_id text not null,
  merchant_id text not null,
  device_id text not null,
  ip_address inet not null,
  amount numeric not null,
  occurred_at timestamptz not null,
  fraud_probability numeric,
  confidence numeric,
  severity text,
  shap_explanations jsonb not null default '[]'::jsonb,
  graph_features jsonb not null default '{}'::jsonb,
  model_version text not null,
  feature_schema_version text not null,
  created_at timestamptz not null default now()
);

create table if not exists feedback (
  id bigserial primary key,
  transaction_id text not null references transactions(transaction_id),
  corrected_label boolean not null,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists model_registry (
  id bigserial primary key,
  model_version text unique not null,
  feature_schema_version text not null,
  ordered_features jsonb not null,
  feature_count integer not null,
  preprocessing_config jsonb not null default '{}'::jsonb,
  metrics jsonb not null,
  is_active boolean not null default false,
  deployed_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists graph_features (
  id bigserial primary key,
  transaction_id text not null references transactions(transaction_id),
  graph_degree integer not null,
  clustering_coefficient numeric not null,
  ring_detected boolean not null,
  shared_entities jsonb not null default '[]'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists graph_relationships (
  id bigserial primary key,
  node_id text not null,
  node_type text not null,
  edge_type text not null,
  connected_node_id text not null,
  connected_node_type text not null,
  observed_at timestamptz not null,
  created_at timestamptz not null default now()
);

create table if not exists alerts (
  id bigserial primary key,
  transaction_id text not null references transactions(transaction_id),
  severity text not null,
  notification_state text not null default 'pending',
  acknowledged_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists fraud_patterns (
  id bigserial primary key,
  source text not null,
  title text not null,
  summary text not null,
  evidence jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
