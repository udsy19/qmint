import type { Metadata } from "next";
import { RouteStub } from "@/components/route-stub";

export const metadata: Metadata = { title: "Quantum vs classical" };

export default function Page() {
  return <RouteStub route="/benchmarks" title="Quantum vs classical" owner="Agent E (benchmarks)" summary="Latency benchmarks with matched assumptions; classical baselines not available until lane H merges — GET /api/v1/benchmarks." />;
}
