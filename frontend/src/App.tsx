import { lazy, Suspense, useState, type ReactNode } from "react";
import { localeNames, supportedLocales, translationStatus, useLocale, type MessageKey } from "./i18n";
import DriverExperience from "./DriverExperience";
import ResidentExperience from "./ResidentExperience";
import FieldWorkerExperience from "./FieldWorkerExperience";
import SignIn from "./SignIn";
const EvidenceExperience = lazy(() => import("./EvidenceExperience"));
const ForecastExperience = lazy(() => import("./ForecastExperience"));
const PlanExperience = lazy(() => import("./PlanExperience"));
const ExplainExperience = lazy(() => import("./ExplainExperience"));
const ImpactExperience = lazy(() => import("./ImpactExperience"));

type Workspace = "officer" | "resident" | "fieldWorker" | "driver";
type IconName = "overview" | "atlas" | "plan" | "impact" | "help" | "water" | "report" | "route" | "proof" | "settings" | "arrow" | "location" | "check";

const navByWorkspace: Record<Workspace, { key: MessageKey; icon: IconName }[]> = {
  officer: [
    { key: "officerOverview", icon: "overview" },
    { key: "officerWaterAccess", icon: "atlas" },
    { key: "officerForecast", icon: "impact" },
    { key: "officerAllocationPlan", icon: "plan" },
    { key: "officerImpact", icon: "impact" },
    { key: "officerExplain", icon: "help" },
  ],
  resident: [
    { key: "residentHome", icon: "overview" },
    { key: "residentRequests", icon: "water" },
    { key: "residentReport", icon: "report" },
    { key: "residentUpdates", icon: "impact" },
  ],
  fieldWorker: [
    { key: "fieldWorkerNewReport", icon: "report" },
    { key: "fieldWorkerQueue", icon: "water" },
  ],
  driver: [
    { key: "driverRoute", icon: "route" },
    { key: "driverProof", icon: "proof" },
    { key: "help", icon: "help" },
  ],
};

function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const common = { width: size, height: size, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.8, strokeLinecap: "round" as const, strokeLinejoin: "round" as const, "aria-hidden": true as const };
  const paths: Record<IconName, ReactNode> = {
    overview: <><rect x="3.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="3.5" width="7" height="7" rx="1.5" /><rect x="3.5" y="13.5" width="7" height="7" rx="1.5" /><rect x="13.5" y="13.5" width="7" height="7" rx="1.5" /></>,
    atlas: <><path d="M12 21s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z" /><circle cx="12" cy="9" r="2.2" /></>,
    plan: <><path d="M8 6h12M8 12h12M8 18h12" /><path d="M3.5 6h.01M3.5 12h.01M3.5 18h.01" /></>,
    impact: <><path d="M4 19V5M4 19h17" /><path d="m7 15 4-4 3 2 6-7" /></>,
    help: <><circle cx="12" cy="12" r="9" /><path d="M9.7 9a2.4 2.4 0 1 1 4.2 1.6c-1 .9-1.9 1.2-1.9 2.9M12 17h.01" /></>,
    water: <><path d="M12 3.5S5.5 11 5.5 15.3a6.5 6.5 0 0 0 13 0C18.5 11 12 3.5 12 3.5Z" /><path d="M9 16a3 3 0 0 0 3 3" /></>,
    report: <><path d="M12 3.5 21 20H3L12 3.5Z" /><path d="M12 9v4.5M12 17h.01" /></>,
    route: <><circle cx="6" cy="18" r="2.2" /><circle cx="18" cy="6" r="2.2" /><path d="M8.2 18c7.5 0 1-12 7.6-12" /></>,
    proof: <><path d="M7 3.5h10l3 3V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1.5 1.5 0 0 1 1.5-1.5Z" /><path d="M8 12.5 10.5 15 16 9.5" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="m19.4 15 .1.1 1.2.9-1.2 2.1-1.4-.5a7.8 7.8 0 0 1-1.5.9l-.2 1.5h-2.5l-.3-1.5a7.8 7.8 0 0 1-1.5-.9l-1.4.5-1.2-2.1 1.2-.9a7 7 0 0 1 0-1.8l-1.2-.9 1.2-2.1 1.4.5a7.8 7.8 0 0 1 1.5-.9l.3-1.5h2.5l.2 1.5a7.8 7.8 0 0 1 1.5.9l1.4-.5 1.2 2.1-1.2.9a7 7 0 0 1 0 1.8Z" /></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    location: <><path d="M12 21s7-6.1 7-12a7 7 0 1 0-14 0c0 5.9 7 12 7 12Z" /><circle cx="12" cy="9" r="2" /></>,
    check: <path d="m5 12.5 4.5 4.5L19 7" />,
  };
  return <svg {...common}>{paths[name]}</svg>;
}

const workspaceNames: Record<Workspace, { title: MessageKey; description: MessageKey; eyebrow: MessageKey }> = {
  officer: { title: "officerConsole", description: "officerDescription", eyebrow: "operationsWorkspace" },
  resident: { title: "residentApp", description: "residentDescription", eyebrow: "communityAccess" },
  fieldWorker: { title: "fieldWorkerApp", description: "fieldWorkerDescription", eyebrow: "fieldOperations" },
  driver: { title: "driverApp", description: "driverDescription", eyebrow: "fieldOperations" },
};

function Brand() {
  const { t } = useLocale();
  return <div className="brand-lockup"><span className="brand-mark"><Icon name="water" size={22} /></span><span><strong>JalLekha</strong><small>{t("brandTagline")}</small></span></div>;
}

function WorkspaceSwitcher({ value, onChange }: { value: Workspace; onChange: (workspace: Workspace) => void }) {
  const { t, locale, setLocale } = useLocale();
  const workspaceLabel: Record<Workspace, MessageKey> = { officer: "officer", resident: "resident", fieldWorker: "fieldWorker", driver: "driver" };
  return (
    <div className="topbar-controls">
    <label className="language-picker"><span className="sr-only">{t("language")}</span><select aria-label={t("language")} value={locale} onChange={(event) => setLocale(event.target.value as (typeof supportedLocales)[number])}>{supportedLocales.map((item) => <option key={item} value={item}>{localeNames[item]}</option>)}</select></label>
    <label className="mobile-workspace-picker"><span className="sr-only">{t("chooseWorkspace")}</span><select aria-label={t("chooseWorkspace")} value={value} onChange={(event) => onChange(event.target.value as Workspace)}>{(["officer", "resident", "fieldWorker", "driver"] as const).map((workspace) => <option key={workspace} value={workspace}>{t(workspaceLabel[workspace])}</option>)}</select></label>
    <div className="workspace-switcher" role="group" aria-label={t("chooseWorkspace")}>
      {(["officer", "resident", "fieldWorker", "driver"] as const).map((workspace) => (
        <button key={workspace} className={value === workspace ? "workspace-tab active" : "workspace-tab"} onClick={() => onChange(workspace)} aria-pressed={value === workspace}>
          {t(workspaceLabel[workspace])}
        </button>
      ))}
    </div>
    </div>
  );
}

function Sidebar({ workspace, activeItem, onNavigate }: { workspace: Workspace; activeItem: MessageKey; onNavigate: (label: MessageKey) => void }) {
  const { t } = useLocale();
  const meta = workspaceNames[workspace];
  return (
    <aside className="sidebar">
      <Brand />
      <div className="sidebar-rule" />
      <p className="sidebar-label">{t(meta.eyebrow)}</p>
      <nav className="side-nav" aria-label={t("navigation")}>
        {navByWorkspace[workspace].map((item) => (
          <button key={item.key} className={activeItem === item.key ? "nav-item selected" : "nav-item"} onClick={() => onNavigate(item.key)} aria-current={activeItem === item.key ? "page" : undefined}>
            <Icon name={item.icon} /><span>{t(item.key)}</span>{activeItem === item.key && <span className="nav-indicator" />}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="offline-chip"><span className="status-dot" />{t("demoWorkspace")}</div>
        <button className="profile-button"><span className="avatar">JL</span><span className="profile-copy"><strong>{t(workspace === "resident" ? "yourAccount" : workspace === "fieldWorker" ? "fieldWorkerProfile" : workspace === "driver" ? "driverProfile" : "officerProfile")}</strong><small>{t("hyderabadTelangana")}</small></span><Icon name="settings" size={18} /></button>
      </div>
    </aside>
  );
}

function MobileNavigation({ workspace, activeItem, onNavigate }: { workspace: Workspace; activeItem: MessageKey; onNavigate: (label: MessageKey) => void }) {
  const { t } = useLocale();
  return <nav className="mobile-nav" aria-label={t("navigation")}>{navByWorkspace[workspace].map((item) => <button key={item.key} className={activeItem === item.key ? "mobile-nav-item selected" : "mobile-nav-item"} onClick={() => onNavigate(item.key)} aria-current={activeItem === item.key ? "page" : undefined}><Icon name={item.icon} size={18} /><span>{t(item.key)}</span></button>)}</nav>;
}

function PlaceholderPage({ workspace, pageKey }: { workspace: Workspace; pageKey: MessageKey }) {
  const { t } = useLocale();
  return <section className="placeholder-page"><span className="placeholder-icon"><Icon name={navByWorkspace[workspace].find((item) => item.key === pageKey)?.icon ?? "overview"} size={25} /></span><p className="eyebrow">{t("workspaceSection")}</p><h1>{t(pageKey)}</h1><p>{t("sectionPlaceholder")}</p><span className="prototype-note">{t("shellPreview")}</span></section>;
}

function SourceTag({ kind }: { kind: "REAL" | "DERIVED" | "SIMULATION" }) {
  return <span className={`source-tag ${kind.toLowerCase()}`}>{kind}</span>;
}

function OfficerHome({ onNavigate }: { onNavigate: (key: MessageKey) => void }) {
  const { t } = useLocale();
  return (
    <>
      <div className="welcome-row"><div><p className="eyebrow">{t("planningWorkspace")}</p><h1>{t("goodMorning")}</h1><p className="muted">{t("officerIntro")}</p></div><button className="button button-secondary"><Icon name="location" size={18} /> {t("hyderabad")} <span className="chevron">⌄</span></button></div>
      <section className="notice-bar"><span className="notice-icon"><Icon name="check" size={18} /></span><p><strong>{t("evidenceBeforeAllocation")}</strong><span>{t("reviewDataBasis")}</span></p><span className="notice-link">{t("readGuide")} <Icon name="arrow" size={16} /></span></section>
      <div className="section-heading"><div><h2>{t("atAGlance")}</h2><p className="muted">{t("currentEvidence")}</p></div><span className="updated-label"><span className="status-dot" /> {t("readyToReview")}</span></div>
      <div className="metric-grid">
        <article className="metric-card"><div className="metric-top"><span className="metric-icon teal"><Icon name="atlas" /></span><SourceTag kind="REAL" /></div><p className="metric-label">{t("waterAccessEvidence")}</p><strong className="metric-value">{t("wardLevel")}</strong><p className="metric-note">{t("censusBaseline")}</p></article>
        <article className="metric-card"><div className="metric-top"><span className="metric-icon blue"><Icon name="water" /></span><SourceTag kind="DERIVED" /></div><p className="metric-label">{t("serviceCoverage")}</p><strong className="metric-value">{t("readyToReview")}</strong><p className="metric-note">{t("exploreNeed")}</p></article>
        <article className="metric-card"><div className="metric-top"><span className="metric-icon amber"><Icon name="plan" /></span><SourceTag kind="SIMULATION" /></div><p className="metric-label">{t("allocationWorkspace")}</p><strong className="metric-value">{t("noPlanPending")}</strong><p className="metric-note">{t("officerReviewPlan")}</p></article>
      </div>
      <div className="content-grid">
        <section className="panel focus-panel"><div className="panel-heading"><div><p className="eyebrow">{t("startHere")}</p><h2>{t("buildFairPicture")}</h2></div><span className="panel-mark"><Icon name="atlas" size={21} /></span></div><p className="panel-copy">{t("fairPictureCopy")}</p><button className="text-button" onClick={() => onNavigate("officerWaterAccess")}>{t("openWaterAccess")} <Icon name="arrow" size={17} /></button><div className="mini-legend"><span><i className="legend-dot teal-dot" />{t("accessNeed")}</span><span><i className="legend-dot blue-dot" />{t("serviceHistory")}</span><span><i className="legend-dot amber-dot" />{t("needsReview")}</span></div></section>
        <section className="panel checklist-panel"><div className="panel-heading"><div><p className="eyebrow">{t("yourWorkflow")}</p><h2>{t("planningChecklist")}</h2></div><span className="quiet-count">{t("checklistCount")}</span></div><ol className="checklist"><li className="complete"><span className="step-check"><Icon name="check" size={14} /></span><span><strong>{t("reviewEvidence")}</strong><small>{t("understandData")}</small></span></li><li><span className="step-number">2</span><span><strong>{t("comparePatterns")}</strong><small>{t("fieldCheckPrompt")}</small></span></li><li><span className="step-number">3</span><span><strong>{t("reviewProposedPlan")}</strong><small>{t("approvalReason")}</small></span></li></ol></section>
      </div>
      <p className="honesty-note"><span className="honesty-mark">i</span>{t("historicalApproximate")} {t("flagNotProof")}</p>
    </>
  );
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace>("officer");
  const [activeItem, setActiveItem] = useState<MessageKey>("officerOverview");
  const { direction, locale, t } = useLocale();
  const meta = workspaceNames[workspace];

  function changeWorkspace(next: Workspace) {
    setWorkspace(next);
    setActiveItem(navByWorkspace[next][0].key);
  }

  return (
    <div className="app-frame" dir={direction} lang={locale}>
      <Sidebar workspace={workspace} activeItem={activeItem} onNavigate={setActiveItem} />
      <div className="main-column">
        <header className="topbar"><div className="mobile-brand"><Brand /></div><div className="topbar-context"><span className="topbar-kicker">JALLEKHA 2.0</span><span className="topbar-divider">/</span><span>{t(meta.title)}</span></div><WorkspaceSwitcher value={workspace} onChange={changeWorkspace} /><SignIn /><button className="help-button" aria-label={t("help")}><Icon name="help" size={20} /></button></header>
        <MobileNavigation workspace={workspace} activeItem={activeItem} onNavigate={setActiveItem} />
        {translationStatus[locale] === "draft" && <p className="translation-draft-note" role="note" aria-label={t("translationStatusLabel")}>{t("translationDraft")}</p>}
        <main className={`page-content ${workspace}-content ${workspace === "officer" && activeItem === "officerWaterAccess" ? "officer-evidence-content" : workspace === "officer" && activeItem === "officerForecast" ? "officer-forecast-content" : workspace === "officer" && activeItem === "officerAllocationPlan" ? "officer-plan-content" : ""}`}>
          <div className="page-title-mobile"><p className="eyebrow">{t(meta.eyebrow)}</p><h1>{t(meta.title)}</h1><p className="muted">{t(meta.description)}</p></div>
          {workspace === "driver" ? <DriverExperience page={activeItem === "driverProof" ? "proof" : activeItem === "help" ? "help" : "route"} onNavigate={setActiveItem} /> : workspace === "resident" ? <ResidentExperience page={activeItem === "residentReport" ? "report" : activeItem === "residentRequests" ? "requests" : activeItem === "residentUpdates" ? "ward" : "home"} onNavigate={setActiveItem} /> : workspace === "fieldWorker" ? <FieldWorkerExperience page={activeItem === "fieldWorkerQueue" ? "queue" : "report"} onNavigate={setActiveItem} /> : activeItem === "officerWaterAccess" ? <Suspense fallback={<p className="muted" role="status">{t("loadingEvidence")}</p>}><EvidenceExperience /></Suspense> : activeItem === "officerForecast" ? <Suspense fallback={<p className="muted" role="status">{t("loadingForecast")}</p>}><ForecastExperience /></Suspense> : activeItem === "officerAllocationPlan" ? <Suspense fallback={<p className="muted" role="status">{t("loadingForecast")}</p>}><PlanExperience /></Suspense> : activeItem === "officerExplain" ? <Suspense fallback={<p className="muted" role="status">{t("loadingForecast")}</p>}><ExplainExperience /></Suspense> : activeItem === "officerImpact" ? <Suspense fallback={<p className="muted" role="status">{t("loadingForecast")}</p>}><ImpactExperience /></Suspense> : activeItem !== navByWorkspace[workspace][0].key ? <PlaceholderPage workspace={workspace} pageKey={activeItem} /> : <OfficerHome onNavigate={setActiveItem} />}
        </main>
        <footer className="app-footer"><span>JalLekha <span className="footer-separator">·</span> {t("footerTagline")}</span><span>{t("footerPromise")}</span></footer>
      </div>
    </div>
  );
}
