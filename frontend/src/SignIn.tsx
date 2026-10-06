import { useId, useState, type FormEvent } from "react";
import { useAuth } from "./auth";
import { useLocale, type MessageKey } from "./i18n";

const roleLabel: Record<string, MessageKey> = {
  officer: "officer",
  driver: "driver",
  resident: "resident",
  field_worker: "fieldWorker",
  councillor: "councillor",
};

export default function SignIn() {
  const { t } = useLocale();
  const { status, role, userId, open: openServer, signIn, signOut } = useAuth();
  const [open, setOpen] = useState(false);
  const [token, setTokenText] = useState("");
  const fieldId = useId();

  async function submit(event: FormEvent) {
    event.preventDefault();
    await signIn(token);
    setTokenText("");
  }

  if (openServer) return null; // the server asks nobody to sign in

  if (status === "signed-in" && role) {
    return (
      <div className="sign-in-box">
        <span className="sign-in-who">{t("signedInAs")} <strong>{t(roleLabel[role] ?? "officer")}</strong>{userId ? ` · ${userId}` : ""}</span>
        <button className="text-button" onClick={signOut}>{t("signOut")}</button>
      </div>
    );
  }

  return (
    <div className="sign-in-box">
      <button className="button button-secondary" aria-expanded={open} onClick={() => setOpen((value) => !value)}>{t("signIn")}</button>
      {open && (
        <form className="sign-in-form" onSubmit={(event) => void submit(event)}>
          <label htmlFor={fieldId}>{t("accessToken")}</label>
          <input id={fieldId} type="password" autoComplete="off" value={token} onChange={(event) => setTokenText(event.target.value)} />
          <small>{t("accessTokenHelp")}</small>
          <button className="button button-primary" type="submit" disabled={status === "checking" || !token.trim()}>{status === "checking" ? t("checkingToken") : t("continueLabel")}</button>
          {status === "rejected" && <p role="alert" className="sign-in-error">{t("tokenRejected")}</p>}
          {status === "unreachable" && <p role="alert" className="sign-in-error">{t("serverUnreachable")}</p>}
        </form>
      )}
    </div>
  );
}
