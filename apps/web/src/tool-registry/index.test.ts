import { describe, expect, it } from "vitest";

import { buildSidebarTools } from "./index";

describe("buildSidebarTools", () => {
  it("merges toolbox pages with remote tools and sorts by order", () => {
    const items = buildSidebarTools([
      {
        id: "csv-translation",
        title: "CSV 翻译",
        description: "CSV 翻译工具",
        route: "/tools/csv-translation",
        icon: "translation",
        category: "translation",
        enabled: true,
        order: 10,
        capabilities: ["upload", "translation"],
      },
      {
        id: "po-translation",
        title: "PO 翻译",
        description: "PO 翻译工具",
        route: "/tools/po-translation",
        icon: "translation",
        category: "translation",
        enabled: true,
        order: 30,
        capabilities: ["upload", "translation"],
      },
    ]);

    expect(items.map((item) => item.id)).toEqual([
      "home",
      "csv-translation",
      "runs",
      "files",
      "settings",
      "po-translation",
    ]);
  });

  it("marks tools and platform pages with separate sections", () => {
    const items = buildSidebarTools([
      {
        id: "csv-translation",
        title: "CSV 翻译",
        description: "CSV 翻译工具",
        route: "/tools/csv-translation",
        icon: "translation",
        category: "translation",
        enabled: true,
        order: 10,
        capabilities: ["upload", "translation"],
      },
    ]);

    expect(items.map((item) => ({ id: item.id, section: (item as { section?: string }).section }))).toEqual([
      { id: "home", section: "platform" },
      { id: "csv-translation", section: "tool" },
      { id: "runs", section: "platform" },
      { id: "files", section: "platform" },
      { id: "settings", section: "platform" },
    ]);
  });
});
