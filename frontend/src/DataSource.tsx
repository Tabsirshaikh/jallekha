import type { ApiState } from "./useApi";
import { useLocale } from "./i18n";

/** Says where a screen's numbers came from: the live API, or the labelled snapshot shipped with the app. */
export default function DataSourceChip({ state }: { state: Pick<ApiState<unknown>, "live" | "loading" | "error"> }) {
  const { t } = useLocale();
  if (state.loading) return <span className="data-source-chip" role="status">{t("checkingToken")}</span>;
  if (state.live) return <span className="data-source-chip live" role="status"><i className="status-dot" /> {t("dataLive")}</span>;
  return <span className="data-source-chip snapshot" role="status" title={state.error ? t("serverUnreachable") : undefined}>{t("dataSnapshot")}</span>;
}
