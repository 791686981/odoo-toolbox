import { GettextTranslationPage } from "./GettextTranslationPage";

export const gettextTranslationToolPage = {
  id: "gettext-translation",
  route: "/tools/gettext-translation",
  component: GettextTranslationPage,
  buildRunDetailPath: (runId: string) => `/tools/gettext-translation?runId=${encodeURIComponent(runId)}`,
};

export { GettextTranslationPage };
