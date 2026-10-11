import type { Metadata } from "next";
import { RouteStub } from "@/components/route-stub";

export const metadata: Metadata = { title: "Research library" };

export default function Page() {
  return <RouteStub route="/research" title="Research library" owner="Agent C (shell)" summary="Papers, games and protocol notes — GET /api/v1/research/sources." />;
}
