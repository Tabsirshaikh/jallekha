import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";
import { LocaleProvider } from "./i18n";

describe("App", () => {
  it("renders and switches between the officer, resident, and driver workspaces", () => {
    render(
      <LocaleProvider>
        <App />
      </LocaleProvider>,
    );

    expect(screen.getByRole("heading", { name: "Officer console" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Resident" }));
    expect(screen.getByRole("heading", { name: "Water support, made easier." })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Driver" }));
    expect(screen.getByRole("heading", { name: "Your workday" })).toBeInTheDocument();
  });
});
