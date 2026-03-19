import { CsvTranslationPage } from "./CsvTranslationPage";

export const csvTranslationToolPage = {
  id: "csv-translation",
  route: "/tools/csv-translation",
  component: CsvTranslationPage,
  buildRunDetailPath: (runId: string) => `/tools/csv-translation?jobId=${encodeURIComponent(runId)}`,
};

export { CsvTranslationPage };
