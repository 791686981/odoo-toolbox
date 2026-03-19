import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  login: vi.fn(),
}));

vi.mock("../../shared/api/client", () => ({
  api: {
    login: apiMock.login,
  },
}));

import { LoginPage } from "./LoginPage";

describe("LoginPage", () => {
  it("does not prefill the password field", () => {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
        },
      },
    });

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LoginPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const passwordInput = container.querySelector('input[type="password"]');

    expect(passwordInput).not.toBeNull();
    expect(passwordInput).toHaveValue("");
  });
});
