import type { Metadata } from "next";
import { RouteStub } from "@/components/route-stub";

export const metadata: Metadata = { title: "Research overview" };

export default function Page() {
  return <RouteStub route="/app" title="Research overview" owner="Agent C (shell)" summary="Overview of protocols, recent runs and tools, from /api/v1/meta, /protocols and /evidence." />;
}
