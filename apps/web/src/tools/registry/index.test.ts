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

  it("builds the csv translation run detail path", () => {
    expect(getToolRunDetailPath("csv-translation", "job-123")).toBe("/tools/csv-translation?jobId=job-123");
  });

  it("returns null for unknown tool run detail paths", () => {
    expect(getToolRunDetailPath("unknown-tool", "job-123")).toBeNull();
  });
});
