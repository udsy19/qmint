import type { Metadata } from "next";
import { RouteStub } from "@/components/route-stub";

export const metadata: Metadata = { title: "Quantum money laboratory" };

export default function Page() {
  return <RouteStub route="/lab/mint" title="Quantum money laboratory" owner="Agent D (lab)" summary="Configure and mint a Wiesner token (n ≤ 8): preparation, circuit, measurement statistics, provenance — POST /api/v1/lab/mint." />;
}
