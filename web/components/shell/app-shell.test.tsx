import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";

const push = vi.fn();
let pathname = "/research/P01";
vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ push, replace: vi.fn(), prefetch: vi.fn() }),
}));

const apiGet = vi.fn();
vi.mock("@/lib/api/client", async (orig) => ({ ...(await orig<typeof import("@/lib/api/client")>()), apiGet: (...a: unknown[]) => apiGet(...a) }));

import { AppShell } from "./app-shell";
import { SUPPORT_LINE } from "./support";

beforeAll(() => {
  // cmdk / Radix need these in jsdom
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  Element.prototype.scrollIntoView ??= () => {};
});

beforeEach(() => {
  push.mockReset();
  apiGet.mockReset();
  apiGet.mockResolvedValue({ data: { sources: [{ id: "T-MVW12-THM1", title: "Molina, Vidick & Watrous 2012 · Theorem 1", kind: "theorem" }] } });
  window.localStorage.clear();
  pathname = "/research/P01";
});

function renderShell() {
  return render(
    <TooltipProvider>
      <AppShell>
        <main id="main">
          <h1>Page</h1>
        </main>
      </AppShell>
    </TooltipProvider>,
  );
}

describe("AppShell", () => {
  it("renders the required support sentence verbatim", () => {
    renderShell();
    expect(SUPPORT_LINE).toBe("This effort is supported by Qollab & IonQ.");
    expect(screen.getByTestId("support-line")).toHaveTextContent(/^This effort is supported by Qollab & IonQ\.$/);
  });

  it("links license and disclosure from the footer", () => {
    renderShell();
    expect(screen.getByRole("link", { name: "MIT License" })).toHaveAttribute("href", expect.stringMatching(/LICENSE$/));
    expect(screen.getByRole("link", { name: "Disclosure" })).toHaveAttribute("href", expect.stringMatching(/DISCLOSURE\.md$/));
  });

  it("shows every section in the sidebar and marks the current one", () => {
    renderShell();
    const nav = screen.getByRole("navigation", { name: "Platform sections" });
    for (const label of ["Overview", "Mint", "Attack", "Benchmarks", "Certificates", "Research", "Docs"]) {
      expect(within(nav).getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(within(nav).getByRole("link", { name: "Research" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Docs" })).not.toHaveAttribute("aria-current");
  });

  it("renders breadcrumbs with the current page last", () => {
    renderShell();
    const bc = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(bc).getByRole("link", { name: "Research" })).toHaveAttribute("href", "/research");
    expect(within(bc).getByText("P01")).toHaveAttribute("aria-current", "page");
  });

  it("collapses the sidebar to a rail and remembers it", async () => {
    renderShell();
    await userEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toHaveAttribute("aria-expanded", "false");
    expect(window.localStorage.getItem("qmint.sidebar.collapsed")).toBe("1");
    // "[" toggles back
    fireEvent.keyDown(window, { key: "[" });
    expect(screen.getByRole("button", { name: "Collapse sidebar" })).toBeInTheDocument();
  });

  it("opens the command palette with ⌘K and navigates to docs and research entries", async () => {
    renderShell();
    act(() => {
      fireEvent.keyDown(window, { key: "k", metaKey: true });
    });
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("API reference")).toBeInTheDocument();
    expect(await within(dialog).findByText("Molina, Vidick & Watrous 2012 · Theorem 1")).toBeInTheDocument();
    expect(apiGet).toHaveBeenCalledWith("/api/v1/research/sources", expect.anything());

    await userEvent.type(within(dialog).getByRole("combobox"), "Exit codes");
    await userEvent.keyboard("{Enter}");
    expect(push).toHaveBeenCalledWith("/docs/cli#exit-codes");
  });

  it("opens the palette with Ctrl+K and closes it with Escape", async () => {
    renderShell();
    act(() => {
      fireEvent.keyDown(window, { key: "K", ctrlKey: true });
    });
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps working when the research library cannot load", async () => {
    apiGet.mockRejectedValue(new Error("network down"));
    renderShell();
    await userEvent.click(screen.getAllByRole("button", { name: "Open command palette" })[0]!);
    const dialog = await screen.findByRole("dialog");
    expect(await within(dialog).findByText(/entries could not load/)).toBeInTheDocument();
    expect(within(dialog).getByText("Overview")).toBeInTheDocument();
  });
});
