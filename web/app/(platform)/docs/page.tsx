import type { Metadata } from "next";
import { RouteStub } from "@/components/route-stub";

export const metadata: Metadata = { title: "Documentation" };

export default function Page() {
  return <RouteStub route="/docs" title="Documentation" owner="Agent C (shell)" summary="API reference, reproducibility, architecture, limitations and methodology." />;
}
