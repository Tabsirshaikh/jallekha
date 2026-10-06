import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setToken } from "./api";
import App from "./App";
import { AuthProvider } from "./auth";
import { LocaleProvider } from "./i18n";

describe("App", () => {
  beforeEach(() => setToken(null));
  afterEach(() => vi.unstubAllGlobals());

  it("translates resident and driver shells and applies Urdu right-to-left direction", () => {
    const { container } = render(
      <LocaleProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
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
    expect(screen.getByRole("heading", { name: "آج کا راستہ" })).toBeInTheDocument();

    fireEvent.change(languagePicker, { target: { value: "hi" } });
    expect(screen.getByRole("heading", { name: "आज का मार्ग" })).toBeInTheDocument();
  });

  it("signs in with a token and shows the role the server reports", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ role: "officer", user_id: "off-1" }), { status: 200, headers: { "Content-Type": "application/json" } }))));
    render(
      <LocaleProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.change(screen.getByLabelText("Access token"), { target: { value: "t-officer" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getByText(/Signed in as/)).toBeInTheDocument());
    expect(screen.getByText(/off-1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("shows no sign-in button when the server needs no sign-in", async () => {
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify({ role: "dev", user_id: null, open: true }), { status: 200, headers: { "Content-Type": "application/json" } }))));
    render(
      <LocaleProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </LocaleProvider>,
    );
    await waitFor(() => expect(screen.queryByRole("button", { name: "Sign in" })).not.toBeInTheDocument());
    expect(screen.queryByText(/Signed in as/)).not.toBeInTheDocument();
  });

  it("says so when a token is rejected", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "unauthorized", message: "Unknown token" } }), { status: 401, headers: { "Content-Type": "application/json" } })));
    render(
      <LocaleProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </LocaleProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    fireEvent.change(screen.getByLabelText("Access token"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("That token was not accepted."));
  });

  it("says a translation is a draft until a native speaker has reviewed it", () => {
    render(
      <LocaleProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </LocaleProvider>,
    );
    expect(screen.queryByRole("note", { name: "Translation status" })).not.toBeInTheDocument();
    const picker = screen.getByRole("combobox", { name: "Language" });
    fireEvent.change(picker, { target: { value: "te" } });
    expect(screen.getByRole("note", { name: "అనువాద స్థితి" })).toHaveTextContent("ఈ అనువాదం ముసాయిదా");
    fireEvent.change(picker, { target: { value: "ur" } });
    expect(screen.getByRole("note", { name: "ترجمے کی حیثیت" })).toHaveTextContent("یہ ترجمہ مسودہ ہے");
    fireEvent.change(picker, { target: { value: "hi" } });
    expect(screen.getByRole("note", { name: "अनुवाद की स्थिति" })).toHaveTextContent("यह अनुवाद मसौदा है");
  });
});

