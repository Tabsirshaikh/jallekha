/* eslint-disable react-refresh/only-export-components -- the auth hook lives beside its provider. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, apiFetch, getToken, setToken } from "./api";

export type Role = "officer" | "driver" | "resident" | "field_worker" | "councillor";
export type AuthStatus = "anonymous" | "checking" | "signed-in" | "rejected" | "unreachable";

type AuthValue = {
  status: AuthStatus;
  role: Role | null;
  userId: string | null;
  /** True when the server asks nobody to sign in: the role then follows the workspace on screen. */
  open: boolean;
  setWorkspaceRole: (role: Role) => void;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

type Me = { role: Role | "dev"; user_id: string | null; open?: boolean };

// Open server: who the screen acts as. Ids look like the bound ids the token setup uses.
const OPEN_USER: Record<Role, string> = { officer: "officer-01", driver: "driver-01", resident: "resident-01", field_worker: "field-worker-01", councillor: "councillor-01" };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() => (getToken() ? "checking" : "anonymous"));
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const [workspaceRole, setWorkspaceRole] = useState<Role>("officer");

  const accept = useCallback((result: Me) => {
    setMe(result);
    setOpen(result.open === true);
    setStatus("signed-in");
  }, []);

  const refuse = useCallback((cause: unknown) => {
    setMe(null);
    if (cause instanceof ApiError && (cause.status === 401 || cause.status === 403)) {
      setToken(null);
      setStatus("rejected");
    } else {
      // The server could not be asked: keep the token so a retry works once it is back.
      setStatus("unreachable");
    }
  }, []);

  // A token left from earlier in this tab is checked once on load (status starts as "checking").
  // Without one the server is asked once whether it is open (no sign-in needed); if not, or if it
  // cannot be reached, the screens stay signed out exactly as before.
  useEffect(() => {
    let active = true;
    const hadToken = Boolean(getToken());
    apiFetch<Me>("/auth/me")
      .then((result) => active && (hadToken || result.open === true) && accept(result))
      .catch((cause: unknown) => {
        if (!active) return;
        if (hadToken) refuse(cause);
      });
    return () => {
      active = false;
    };
  }, [accept, refuse]);

  const signIn = useCallback(
    async (token: string) => {
      setToken(token.trim() || null);
      if (!getToken()) {
        setMe(null);
        setStatus("anonymous");
        return;
      }
      setStatus("checking");
      try {
        accept(await apiFetch<Me>("/auth/me"));
      } catch (cause) {
        refuse(cause);
      }
    },
    [accept, refuse],
  );

  const signOut = useCallback(() => {
    setToken(null);
    setMe(null);
    setOpen(false);
    setStatus("anonymous");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({
      status,
      // An open server answers as "dev" (allowed everywhere); the screen acts as its workspace's role.
      role: open ? workspaceRole : ((me?.role as Role | undefined) ?? null), // the dev token keeps role "dev"
      userId: open ? OPEN_USER[workspaceRole] : me?.user_id ?? null,
      open,
      setWorkspaceRole,
      signIn,
      signOut,
    }),
    [status, me, open, workspaceRole, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
