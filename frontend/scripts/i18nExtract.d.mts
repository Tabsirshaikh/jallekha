export type Locale = "en" | "te" | "ur" | "hi";
export type Entry = { file: string; block: number; key: string; en: string | null; te: string | null; ur: string | null; hi: string | null };
export declare const LOCALES: readonly Locale[];
export declare const SCRIPTS: Record<"te" | "ur" | "hi", RegExp>;
export declare function placeholders(text: string): string;
export declare function isProse(text: string): boolean;
export declare function extractTranslations(sources: Record<string, string>): Entry[];
export declare function toCsv(entries: Entry[]): string;
