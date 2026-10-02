import { useState, type ReactNode } from "react";
import { useLocale } from "./i18n";

type Workspace = "officer" | "resident" | "driver";
type IconName = "overview" | "atlas" | "plan" | "impact" | "help" | "water" | "report" | "route" | "proof" | "settings" | "arrow" | "location" | "check";

const navByWorkspace: Record<Workspace, { label: string; icon: IconName }[]> = {
  officer: [
    { label: "Overview", icon: "overview" },
    { label: "Water access", icon: "atlas" },
    { label: "Allocation plan", icon: "plan" },
    { label: "Impact", icon: "impact" },
  ],
  resident: [
    { label: "Home", icon: "overview" },
    { label: "My requests", icon: "water" },
    { label: "Report an issue", icon: "report" },
    { label: "Ward updates", icon: "impact" },
  ],
  driver: [
    { label: "Today’s route", icon: "route" },
    { label: "Delivery proof", icon: "proof" },
    { label: "Help", icon: "help" },
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

const workspaceNames: Record<Workspace, { title: string; description: string; eyebrow: string }> = {
  officer: { title: "Officer console", description: "Evidence-led planning and service oversight", eyebrow: "Operations workspace" },
  resident: { title: "Resident app", description: "Water updates and support for your neighbourhood", eyebrow: "Community access" },
  driver: { title: "Driver app", description: "Your assigned trips and delivery confirmation", eyebrow: "Field operations" },
};

function Brand() {
  return <div className="brand-lockup"><span className="brand-mark"><Icon name="water" size={22} /></span><span><strong>JalLekha</strong><small>WATER, SHARED FAIRLY</small></span></div>;
}

function WorkspaceSwitcher({ value, onChange }: { value: Workspace; onChange: (workspace: Workspace) => void }) {
  return (
    <div className="workspace-switcher" role="group" aria-label="Choose a workspace">
      {(["officer", "resident", "driver"] as const).map((workspace) => (
        <button key={workspace} className={value === workspace ? "workspace-tab active" : "workspace-tab"} onClick={() => onChange(workspace)} aria-pressed={value === workspace}>
          {workspace === "officer" ? "Officer" : workspace === "resident" ? "Resident" : "Driver"}
        </button>
      ))}
    </div>
  );
}

function Sidebar({ workspace, activeItem, onNavigate }: { workspace: Workspace; activeItem: string; onNavigate: (label: string) => void }) {
  const meta = workspaceNames[workspace];
  return (
    <aside className="sidebar">
      <Brand />
      <div className="sidebar-rule" />
      <p className="sidebar-label">{meta.eyebrow}</p>
      <nav className="side-nav" aria-label={`${workspace} navigation`}>
        {navByWorkspace[workspace].map((item) => (
          <button key={item.label} className={activeItem === item.label ? "nav-item selected" : "nav-item"} onClick={() => onNavigate(item.label)} aria-current={activeItem === item.label ? "page" : undefined}>
            <Icon name={item.icon} /><span>{item.label}</span>{activeItem === item.label && <span className="nav-indicator" />}
          </button>
        ))}
      </nav>
      <div className="sidebar-bottom">
        <div className="offline-chip"><span className="status-dot" />Demo workspace</div>
        <button className="profile-button"><span className="avatar">JL</span><span className="profile-copy"><strong>{workspace === "resident" ? "Your account" : workspace === "driver" ? "Driver profile" : "Officer profile"}</strong><small>Hyderabad, Telangana</small></span><Icon name="settings" size={18} /></button>
      </div>
    </aside>
  );
}

function MobileNavigation({ workspace, activeItem, onNavigate }: { workspace: Workspace; activeItem: string; onNavigate: (label: string) => void }) {
  return <nav className="mobile-nav" aria-label={`${workspace} navigation`}>{navByWorkspace[workspace].map((item) => <button key={item.label} className={activeItem === item.label ? "mobile-nav-item selected" : "mobile-nav-item"} onClick={() => onNavigate(item.label)} aria-current={activeItem === item.label ? "page" : undefined}><Icon name={item.icon} size={18} /><span>{item.label}</span></button>)}</nav>;
}

function PlaceholderPage({ workspace, label }: { workspace: Workspace; label: string }) {
  return <section className="placeholder-page"><span className="placeholder-icon"><Icon name={navByWorkspace[workspace].find((item) => item.label === label)?.icon ?? "overview"} size={25} /></span><p className="eyebrow">Workspace section</p><h1>{label}</h1><p>This section is part of the JalLekha workspace. Its feature view will be added in the next implementation step.</p><span className="prototype-note">Shell preview · No live data is connected</span></section>;
}

function SourceTag({ kind }: { kind: "REAL" | "DERIVED" | "SIMULATION" }) {
  return <span className={`source-tag ${kind.toLowerCase()}`}>{kind}</span>;
}

function OfficerHome() {
  return (
    <>
      <div className="welcome-row"><div><p className="eyebrow">Planning workspace</p><h1>Good morning</h1><p className="muted">A clear view of water access, service, and the work ahead.</p></div><button className="button button-secondary"><Icon name="location" size={18} /> Hyderabad <span className="chevron">⌄</span></button></div>
      <section className="notice-bar"><span className="notice-icon"><Icon name="check" size={18} /></span><p><strong>Evidence before allocation</strong><span>Review the data basis and confidence before approving a plan.</span></p><span className="notice-link">Read the guide <Icon name="arrow" size={16} /></span></section>
      <div className="section-heading"><div><h2>At a glance</h2><p className="muted">Current evidence available for planning</p></div><span className="updated-label"><span className="status-dot" /> Workspace ready</span></div>
      <div className="metric-grid">
        <article className="metric-card"><div className="metric-top"><span className="metric-icon teal"><Icon name="atlas" /></span><SourceTag kind="REAL" /></div><p className="metric-label">Water access evidence</p><strong className="metric-value">Ward-level</strong><p className="metric-note">Census baseline, with source age shown</p></article>
        <article className="metric-card"><div className="metric-top"><span className="metric-icon blue"><Icon name="water" /></span><SourceTag kind="DERIVED" /></div><p className="metric-label">Service and coverage</p><strong className="metric-value">Ready to review</strong><p className="metric-note">Explore need alongside booking history</p></article>
        <article className="metric-card"><div className="metric-top"><span className="metric-icon amber"><Icon name="plan" /></span><SourceTag kind="SIMULATION" /></div><p className="metric-label">Allocation workspace</p><strong className="metric-value">No plan pending</strong><p className="metric-note">A plan will need officer review to proceed</p></article>
      </div>
      <div className="content-grid">
        <section className="panel focus-panel"><div className="panel-heading"><div><p className="eyebrow">Start here</p><h2>Build a fair picture</h2></div><span className="panel-mark"><Icon name="atlas" size={21} /></span></div><p className="panel-copy">See where households face barriers to water access, then compare that evidence with tanker service over time.</p><button className="text-button">Open water access <Icon name="arrow" size={17} /></button><div className="mini-legend"><span><i className="legend-dot teal-dot" />Access need</span><span><i className="legend-dot blue-dot" />Service history</span><span><i className="legend-dot amber-dot" />Needs review</span></div></section>
        <section className="panel checklist-panel"><div className="panel-heading"><div><p className="eyebrow">Your workflow</p><h2>Planning checklist</h2></div><span className="quiet-count">01 / 03</span></div><ol className="checklist"><li className="complete"><span className="step-check"><Icon name="check" size={14} /></span><span><strong>Review the evidence</strong><small>Understand what the data can tell you</small></span></li><li><span className="step-number">2</span><span><strong>Compare service patterns</strong><small>Look for places to check with the community</small></span></li><li><span className="step-number">3</span><span><strong>Review a proposed plan</strong><small>Approve only with a recorded reason</small></span></li></ol></section>
      </div>
      <p className="honesty-note"><span className="honesty-mark">i</span>Historical and approximate data is labelled where it appears. A flag is a prompt to investigate, not proof of neglect.</p>
    </>
  );
}

function ResidentHome() {
  return (
    <div className="resident-page">
      <section className="resident-hero"><div className="resident-hero-copy"><p className="eyebrow">Your neighbourhood · Hyderabad</p><h1>Water support,<br />made easier.</h1><p>Check updates, tell us what is happening, or get help from a field worker.</p><button className="button button-dark">Get help <Icon name="arrow" size={18} /></button></div><div className="water-art" aria-hidden="true"><span className="sun-orb" /><span className="water-drop"><Icon name="water" size={70} /></span><span className="art-ripple ripple-one" /><span className="art-ripple ripple-two" /></div></section>
      <div className="resident-notice"><span className="notice-icon"><Icon name="location" size={18} /></span><span><strong>Choose your ward to see local updates</strong><small>Your ward helps us show the right schedule and service information.</small></span><button className="text-button">Choose ward <Icon name="arrow" size={17} /></button></div>
      <div className="section-heading resident-section-heading"><div><h2>What would you like to do?</h2><p className="muted">Choose an option to continue</p></div></div>
      <div className="action-grid">
        <button className="action-card"><span className="action-icon teal"><Icon name="water" size={23} /></span><span className="action-copy"><strong>Track a request</strong><small>See the latest update on your water request</small></span><Icon name="arrow" size={18} /></button>
        <button className="action-card"><span className="action-icon coral"><Icon name="report" size={23} /></span><span className="action-copy"><strong>Report a water issue</strong><small>Tell us about a shortage, leak, or missed tanker</small></span><Icon name="arrow" size={18} /></button>
        <button className="action-card"><span className="action-icon blue"><Icon name="impact" size={23} /></span><span className="action-copy"><strong>See ward updates</strong><small>Read local water access and service information</small></span><Icon name="arrow" size={18} /></button>
      </div>
      <div className="human-help"><span className="help-avatar"><Icon name="help" size={21} /></span><span><strong>Would you rather speak to someone?</strong><small>A field worker can help you make a report.</small></span><button className="button button-secondary">Ask for help</button></div>
      <p className="prototype-note">Demo workspace · No request will be sent to a live service.</p>
    </div>
  );
}

function DriverHome() {
  return (
    <div className="driver-page">
      <div className="driver-heading"><div><p className="eyebrow">Driver workspace</p><h1>Your workday</h1><p className="muted">Route and delivery details assigned to you.</p></div><span className="driver-status"><span className="status-dot" />Ready</span></div>
      <section className="driver-route-card"><div className="route-card-top"><div><span className="route-label">TODAY’S ROUTE</span><h2>No route assigned</h2></div><span className="route-icon"><Icon name="route" size={23} /></span></div><p>Your assigned stops will appear here when a route is ready.</p><div className="route-summary"><div><small>Stops</small><strong>—</strong></div><div><small>First stop</small><strong>—</strong></div><div><small>Route status</small><strong>Waiting</strong></div></div></section>
      <div className="driver-section-title"><h2>At each stop</h2><p className="muted">A simple record keeps deliveries clear for everyone.</p></div>
      <div className="driver-steps"><article className="driver-step"><span className="driver-step-icon"><Icon name="location" /></span><div><strong>Arrive at the stop</strong><p>Confirm your location when you reach the delivery point.</p></div><span className="step-number">1</span></article><article className="driver-step"><span className="driver-step-icon"><Icon name="proof" /></span><div><strong>Confirm delivery with OTP</strong><p>Ask a registered representative for the delivery code.</p></div><span className="step-number">2</span></article><article className="driver-step"><span className="driver-step-icon"><Icon name="check" /></span><div><strong>Record the outcome</strong><p>Save what happened, even if there is a problem.</p></div><span className="step-number">3</span></article></div>
      <div className="driver-footer-note"><Icon name="help" size={18} /><span>Having trouble with GPS? Your app will show when location is unavailable.</span><button className="text-button">Get help</button></div>
      <p className="prototype-note">Demo workspace · No route or delivery is connected to live operations.</p>
    </div>
  );
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace>("officer");
  const [activeItem, setActiveItem] = useState("Overview");
  const { direction, locale, t } = useLocale();
  const meta = workspaceNames[workspace];

  function changeWorkspace(next: Workspace) {
    setWorkspace(next);
    setActiveItem(navByWorkspace[next][0].label);
  }

  return (
    <div className="app-frame" dir={direction} lang={locale}>
      <Sidebar workspace={workspace} activeItem={activeItem} onNavigate={setActiveItem} />
      <div className="main-column">
        <header className="topbar"><div className="mobile-brand"><Brand /></div><div className="topbar-context"><span className="topbar-kicker">JALLEKHA 2.0</span><span className="topbar-divider">/</span><span>{meta.title}</span></div><WorkspaceSwitcher value={workspace} onChange={changeWorkspace} /><button className="help-button" aria-label={t("help")}><Icon name="help" size={20} /></button></header>
        <MobileNavigation workspace={workspace} activeItem={activeItem} onNavigate={setActiveItem} />
        <main className={`page-content ${workspace}-content`}>
          <div className="page-title-mobile"><p className="eyebrow">{meta.eyebrow}</p><h1>{meta.title}</h1><p className="muted">{meta.description}</p></div>
          {activeItem !== navByWorkspace[workspace][0].label ? <PlaceholderPage workspace={workspace} label={activeItem} /> : workspace === "officer" ? <OfficerHome /> : workspace === "resident" ? <ResidentHome /> : <DriverHome />}
        </main>
        <footer className="app-footer"><span>JalLekha <span className="footer-separator">·</span> Community water-supply allocation</span><span>Built for clarity, fairness, and accountability</span></footer>
      </div>
    </div>
  );
}
