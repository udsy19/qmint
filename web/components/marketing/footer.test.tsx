import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MarketingFooter } from "./footer";

describe("<MarketingFooter/>", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("shows the exact support sentence, MIT licence and AI disclosure links, even with the API offline", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new Error("offline"))));
    render(await MarketingFooter());
    expect(screen.getByText("This effort is supported by Qollab & IonQ.")).toBeVisible();
    expect(screen.getByRole("link", { name: /MIT License/ })).toHaveAttribute("href", "https://github.com/udsy19/qmint/blob/main/LICENSE");
    expect(screen.getByRole("link", { name: /AI assistance disclosure/ })).toHaveAttribute("href", "https://github.com/udsy19/qmint/blob/main/DISCLOSURE.md");
    expect(screen.getByText(/API offline/)).toBeInTheDocument();
  });
});
