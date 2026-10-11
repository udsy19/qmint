import type { Metadata, Viewport } from "next";
import { StaticBanner } from "@/components/static-banner";
import { Toaster } from "@/components/ui/toast";
import { TooltipProvider } from "@/components/ui/tooltip";
import { fontVariables } from "@/lib/fonts";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "QMint — quantum payment security research", template: "%s · QMint" },
  description:
    "Open-source research platform for quantum money and payment security: reproducible experiments, attack simulations and labelled evidence. Research demonstrations, not a payment service.",
};

export const viewport: Viewport = { themeColor: "#08090b", colorScheme: "dark" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`dark ${fontVariables}`}>
      <body className="min-h-dvh bg-background font-sans text-foreground">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-tooltip focus:rounded-sm focus:bg-surface-overlay focus:px-3 focus:py-2 focus:text-sm"
        >
          Skip to content
        </a>
        <StaticBanner />
        <TooltipProvider delayDuration={300}>{children}</TooltipProvider>
        <Toaster />
      </body>
    </html>
  );
}
