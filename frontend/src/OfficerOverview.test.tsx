import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { setToken } from "./api";
import { AuthProvider } from "./auth";
import { LocaleProvider } from "./i18n";
import OfficerOverview from "./OfficerOverview";

it("counts exact-section flags on the overview instead of the old six ward flags", () => {
  setToken(null);
  render(<LocaleProvider><AuthProvider><OfficerOverview onNavigate={() => {}} /></AuthProvider></LocaleProvider>);
  const card = screen.getByRole("button", { name: /^Sections with low bookings to check/ });
  expect(within(card).getByText("12")).toBeInTheDocument();
});
