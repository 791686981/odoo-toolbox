import type { ComponentType } from "react";

import { csvTranslationToolPage } from "../csv-translation";

type ToolPageRegistration = {
  id: string;
  route: string;
  component: ComponentType;
  buildRunDetailPath?: (runId: string) => string;
};

export const toolPageRegistrations: ToolPageRegistration[] = [csvTranslationToolPage];

const toolPageRegistrationMap = new Map(toolPageRegistrations.map((registration) => [registration.id, registration]));

export function getToolRunDetailPath(toolId: string, runId: string): string | null {
  return toolPageRegistrationMap.get(toolId)?.buildRunDetailPath?.(runId) ?? null;
}
