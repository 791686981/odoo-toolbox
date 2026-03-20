import { describe, expect, it } from "vitest";

import { getToolRunDetailPath, toolPageRegistrations } from "./index";

describe("toolPageRegistrations", () => {
  it("registers the csv translation page as a standard tool page", () => {
    expect(toolPageRegistrations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "csv-translation",
          route: "/tools/csv-translation",
        }),
      ]),
    );
  });

  it("registers the gettext translation page as a standard tool page", () => {
    expect(toolPageRegistrations).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "gettext-translation",
          route: "/tools/gettext-translation",
        }),
      ]),
    );
  });

  it("builds the csv translation run detail path", () => {
    expect(getToolRunDetailPath("csv-translation", "job-123")).toBe("/tools/csv-translation?jobId=job-123");
  });

  it("builds the gettext translation run detail path", () => {
    expect(getToolRunDetailPath("gettext-translation", "run-123")).toBe(
      "/tools/gettext-translation?runId=run-123",
    );
  });

  it("returns null for unknown tool run detail paths", () => {
    expect(getToolRunDetailPath("unknown-tool", "job-123")).toBeNull();
  });
});
