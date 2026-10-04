/* eslint-disable react-refresh/only-export-components -- the auth hook lives beside its provider. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiError, apiFetch, getToken, setToken } from "./api";

export type Role = "officer" | "driver" | "resident" | "field_worker" | "councillor";
export type AuthStatus = "anonymous" | "checking" | "signed-in" | "rejected" | "unreachable";

type AuthValue = {
  status: AuthStatus;
  role: Role | null;
  userId: string | null;
  signIn: (token: string) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthValue | null>(null);

type Me = { role: Role; user_id: string | null };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>(() => (getToken() ? "checking" : "anonymous"));
  const [me, setMe] = useState<Me | null>(null);

  const accept = useCallback((result: Me) => {
    setMe(result);
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
  useEffect(() => {
    if (!getToken()) return;
    let active = true;
    apiFetch<Me>("/auth/me")
      .then((result) => active && accept(result))
      .catch((cause: unknown) => active && refuse(cause));
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
    setStatus("anonymous");
  }, []);

  const value = useMemo<AuthValue>(
    () => ({ status, role: me?.role ?? null, userId: me?.user_id ?? null, signIn, signOut }),
    [status, me, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
