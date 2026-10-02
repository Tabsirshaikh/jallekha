import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";
import { LocaleProvider } from "./i18n";

describe("App", () => {
  it("translates resident and driver shells and applies Urdu right-to-left direction", () => {
    const { container } = render(
      <LocaleProvider>
        <App />
      </LocaleProvider>,
    );

    expect(screen.getByRole("heading", { name: "Officer console" })).toBeInTheDocument();

    const languagePicker = screen.getByRole("combobox", { name: "Language" });
    fireEvent.change(languagePicker, { target: { value: "te" } });
    fireEvent.click(screen.getByRole("button", { name: "నివాసి" }));
    expect(screen.getByRole("heading", { name: "నీటి సహాయం ఇప్పుడు సులభం." })).toBeInTheDocument();

    fireEvent.change(languagePicker, { target: { value: "ur" } });
    expect(container.querySelector(".app-frame")).toHaveAttribute("dir", "rtl");
    expect(container.querySelector(".app-frame")).toHaveAttribute("lang", "ur");
    fireEvent.click(screen.getByRole("button", { name: "ٹینکر ڈرائیور" }));
    expect(screen.getByRole("heading", { name: "آج کا کام" })).toBeInTheDocument();

    fireEvent.change(languagePicker, { target: { value: "hi" } });
    expect(screen.getByRole("heading", { name: "आज का काम" })).toBeInTheDocument();
  });
});
