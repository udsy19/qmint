import type { Metadata } from "next";
import { RouteStub } from "@/components/route-stub";

export const metadata: Metadata = { title: { absolute: "QMint — quantum payment security research" } };

export default function Page() {
  return <RouteStub route="/" title="QMint" owner="Agent B (landing)" summary="Public landing page: editorial hero, interactive token instrument, sections 01–06." />;
}
