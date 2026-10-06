import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { AuthProvider } from "./auth";
import { setToken } from "./api";
import { LocaleProvider } from "./i18n";
import SectionOutcomeForm from "./SectionOutcomeForm";

beforeEach(() => setToken("t-officer"));
afterEach(() => { setToken(null); vi.unstubAllGlobals(); });

it("records an authenticated visit with a date and note, then refreshes progress", async () => {
  const fetch = vi.fn(async (url: string, options?: RequestInit) => {
    const path = new URL(url, "http://localhost").pathname;
    let body: unknown = { role: "officer", user_id: "officer-1" };
    if (path === "/field-checks/sections") body = { total: 1, items: [{ section_id: "1:CHECK SECTION", section: "CHECK SECTION", division: "1" }] };
    if (path === "/field-checks/summary") body = { decisive_sections: 0, minimum_decisive_sections: 30, precision: null };
    if (options?.method === "POST") body = { ledger_missing: false };
    return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
  });
  vi.stubGlobal("fetch", fetch);
  render(<LocaleProvider><AuthProvider><SectionOutcomeForm /></AuthProvider></LocaleProvider>);
  await screen.findByRole("option", { name: "CHECK SECTION" });
  fireEvent.click(screen.getByLabelText("Yes"));
  fireEvent.change(screen.getByLabelText("Visit date"), { target: { value: "2026-10-05" } });
  fireEvent.change(screen.getByLabelText("Visit note"), { target: { value: "No phone access" } });
  fireEvent.click(screen.getByRole("button", { name: "Save visit outcome" }));
  expect(await screen.findByText("Visit outcome saved")).toBeInTheDocument();
  const post = fetch.mock.calls.find(([, options]) => options?.method === "POST");
  expect(JSON.parse(String(post?.[1]?.body))).toMatchObject({ section_id: "1:CHECK SECTION", could_not_book: "yes", checked_on: "2026-10-05", note: "No phone access" });
  expect(await screen.findByText(/Not yet checked on the ground/)).toBeInTheDocument();
});

it("does not offer recording to signed-out visitors", () => {
  setToken(null);
  vi.stubGlobal("fetch", vi.fn());
  render(<LocaleProvider><AuthProvider><SectionOutcomeForm /></AuthProvider></LocaleProvider>);
  expect(screen.queryByRole("button", { name: "Save visit outcome" })).not.toBeInTheDocument();
});
