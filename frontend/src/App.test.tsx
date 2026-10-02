import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import App from "./App";

describe("App", () => {
  it("renders the JalLekha skeleton status", () => {
    render(<App />);
    expect(screen.getByRole("heading", { name: "JalLekha" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("Project skeleton ready");
  });
});
