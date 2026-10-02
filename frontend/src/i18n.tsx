/* eslint-disable react-refresh/only-export-components -- locale hooks live beside their context provider. */
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

export const supportedLocales = ["en", "te", "ur", "hi"] as const;
export type Locale = (typeof supportedLocales)[number];
export type MessageKey = "appName" | "help" | "overview";

const messages: Record<Locale, Partial<Record<MessageKey, string>>> = {
  en: { appName: "JalLekha", help: "Help", overview: "Overview" },
  te: {},
  ur: {},
  hi: {},
};

type LocaleContextValue = {
  locale: Locale;
  direction: "ltr" | "rtl";
  setLocale: (locale: Locale) => void;
  t: (key: MessageKey) => string;
};

const LocaleContext = createContext<LocaleContextValue | null>(null);

export function LocaleProvider({ children, initialLocale = "en" }: { children: ReactNode; initialLocale?: Locale }) {
  const [locale, setLocale] = useState<Locale>(initialLocale);
  const value = useMemo<LocaleContextValue>(() => ({
    locale,
    direction: locale === "ur" ? "rtl" : "ltr",
    setLocale,
    t: (key) => messages[locale][key] ?? messages.en[key] ?? key,
  }), [locale]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const context = useContext(LocaleContext);
  if (!context) throw new Error("useLocale must be used within LocaleProvider");
  return context;
}
