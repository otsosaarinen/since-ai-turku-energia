import { isHarnessEnabled } from "@/lib/config";
import ForecastViewer from "@/features/forecast/ForecastViewer";

/** The address carries the chosen tab (?method=harness); without it the machine-learning model is shown. */
export default async function Page({ searchParams }: { searchParams: Promise<{ method?: string | string[] }> }) {
  const { method } = await searchParams;
  return <ForecastViewer initialMethod={isHarnessEnabled() && method === "harness" ? "harness" : "current"} />;
}
