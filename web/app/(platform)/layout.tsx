import { AppShell } from "@/components/shell/app-shell";

/**
 * Platform shell layout (Agent C): sidebar, 48px header with breadcrumbs, mobile sheet, global ⌘K palette and
 * the footer carrying the required support line. Pages render their own single <main id="main"> and <h1>.
 */
export default function PlatformLayout({ children }: { children: React.ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
