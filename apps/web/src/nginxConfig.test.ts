import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

describe("nginx api proxy config", () => {
  it("allows large multipart uploads for database backups", () => {
    const config = readFileSync(resolve(process.cwd(), "../../infra/docker/nginx/default.conf"), "utf8");

    expect(config).toMatch(/location \/api\/ \{[\s\S]*client_max_body_size\s+5g;/);
  });
});
