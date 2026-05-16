import { useState } from "react";
import { Shell } from "./components/Shell";
import { Alerts } from "./pages/Alerts";
import { Dashboard } from "./pages/Dashboard";
import { FraudGraph } from "./pages/FraudGraph";
import { FraudIntelligence } from "./pages/FraudIntelligence";
import { ModelHealth } from "./pages/ModelHealth";
import { ShapAnalysis } from "./pages/ShapAnalysis";

const pageMap = {
  dashboard: <Dashboard />,
  graph: <FraudGraph />,
  shap: <ShapAnalysis />,
  model: <ModelHealth />,
  alerts: <Alerts />,
  intelligence: <FraudIntelligence />
};

type PageId = keyof typeof pageMap;

export function App() {
  const [activePage, setActivePage] = useState<PageId>("dashboard");

  return (
    <Shell activePage={activePage} onNavigate={(page) => setActivePage(page as PageId)}>
      {pageMap[activePage]}
    </Shell>
  );
}
