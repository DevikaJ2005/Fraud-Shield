import { Activity, Bell, GitBranch, HeartPulse, LayoutDashboard, Newspaper } from "lucide-react";
import type { ReactNode } from "react";

type ShellProps = {
  activePage: string;
  onNavigate: (page: string) => void;
  children: ReactNode;
};

const pages = [
  { id: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "graph", label: "Fraud Graph", icon: GitBranch },
  { id: "shap", label: "SHAP Analysis", icon: Activity },
  { id: "model", label: "Model Health", icon: HeartPulse },
  { id: "alerts", label: "Alerts", icon: Bell },
  { id: "intelligence", label: "Intelligence", icon: Newspaper }
];

export function Shell({ activePage, onNavigate, children }: ShellProps) {
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-white px-4 py-5 md:block">
        <div className="mb-8">
          <h1 className="text-xl font-semibold tracking-normal">FraudShield</h1>
          <p className="mt-1 text-sm text-slate-500">Graph fraud intelligence</p>
        </div>
        <nav className="space-y-1">
          {pages.map((page) => {
            const Icon = page.icon;
            const active = page.id === activePage;
            return (
              <button
                key={page.id}
                className={`flex w-full items-center gap-3 rounded-md px-3 py-2 text-left text-sm transition ${
                  active ? "bg-ink text-white" : "text-slate-700 hover:bg-panel"
                }`}
                onClick={() => onNavigate(page.id)}
                type="button"
              >
                <Icon size={17} />
                <span>{page.label}</span>
              </button>
            );
          })}
        </nav>
      </aside>
      <main className="md:pl-64">
        <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</div>
      </main>
    </div>
  );
}
