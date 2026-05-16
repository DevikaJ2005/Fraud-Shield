import * as d3 from "d3";
import { useEffect, useRef } from "react";
import type { GraphPayload } from "../api/client";

type SimNode = d3.SimulationNodeDatum & {
  id: string;
  type: string;
};

type SimLink = d3.SimulationLinkDatum<SimNode> & {
  type: string;
};

const colorByType: Record<string, string> = {
  account: "#0f766e",
  device: "#7c3aed",
  ip: "#c2410c",
  merchant: "#2563eb",
  transaction: "#475569",
  unknown: "#64748b"
};

export function GraphCanvas({ graph }: { graph: GraphPayload }) {
  const ref = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();

    const width = 900;
    const height = 420;
    const nodes: SimNode[] = graph.nodes.map((node) => ({ ...node }));
    const links: SimLink[] = graph.links.map((link) => ({ ...link }));

    const simulation = d3
      .forceSimulation(nodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links).id((node) => node.id).distance(70))
      .force("charge", d3.forceManyBody().strength(-180))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide(18));

    const link = svg
      .append("g")
      .attr("stroke", "#cbd5e1")
      .attr("stroke-opacity", 0.8)
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke-width", 1.4);

    const node = svg
      .append("g")
      .selectAll("circle")
      .data(nodes)
      .join("circle")
      .attr("r", 8)
      .attr("fill", (item) => colorByType[item.type] ?? colorByType.unknown)
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 1.5);

    node.append("title").text((item) => item.id);

    simulation.on("tick", () => {
      link
        .attr("x1", (item) => (typeof item.source === "object" ? item.source.x ?? 0 : 0))
        .attr("y1", (item) => (typeof item.source === "object" ? item.source.y ?? 0 : 0))
        .attr("x2", (item) => (typeof item.target === "object" ? item.target.x ?? 0 : 0))
        .attr("y2", (item) => (typeof item.target === "object" ? item.target.y ?? 0 : 0));

      node.attr("cx", (item) => item.x ?? 0).attr("cy", (item) => item.y ?? 0);
    });

    return () => {
      simulation.stop();
    };
  }, [graph]);

  return <svg ref={ref} className="h-[420px] w-full rounded border border-line bg-white" viewBox="0 0 900 420" role="img" />;
}
