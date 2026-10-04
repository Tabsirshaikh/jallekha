/** Why an officer screen is showing its saved snapshot instead of live API data, in plain words. */
import type { ApiError } from "./api";
import type { AuthStatus, Role } from "./auth";
import type { Locale } from "./i18n";

export type LiveReason = "signIn" | "rejected" | "notOfficer" | "unreachable" | "error";

/** Officer-only routes are asked only once the server has confirmed an officer token. */
export function canFetchOfficerData(status: AuthStatus, role: Role | null): boolean {
  return status === "signed-in" && role === "officer";
}

/** `null` while checking or when nothing is wrong. */
export function liveReason(status: AuthStatus, role: Role | null, error: ApiError | null): LiveReason | null {
  if (status === "anonymous") return "signIn";
  if (status === "rejected") return "rejected";
  if (status === "unreachable") return "unreachable";
  if (status === "checking") return null;
  if (role !== "officer") return "notOfficer";
  if (!error) return null;
  if (error.status === 401) return "rejected";
  if (error.status === 403) return "notOfficer";
  if (error.status === 0) return "unreachable";
  return "error";
}

export const liveReasonCopy = {
  en: {
    signIn: "Sign in as an officer to see live data. Showing the saved snapshot.",
    rejected: "Your sign-in was not accepted. Sign in again to see live data. Showing the saved snapshot.",
    notOfficer: "Live data on this screen is for officers. Showing the saved snapshot.",
    unreachable: "The server could not be reached. Showing the saved snapshot.",
    error: "The server returned an error. Showing the saved snapshot.",
  },
  te: {
    signIn: "ప్రత్యక్ష డేటా కోసం అధికారిగా సైన్ ఇన్ చేయండి. సేవ్ చేసిన నమూనా చూపిస్తున్నాం.",
    rejected: "మీ సైన్ ఇన్ అంగీకరించబడలేదు. ప్రత్యక్ష డేటా కోసం మళ్లీ సైన్ ఇన్ చేయండి. సేవ్ చేసిన నమూనా చూపిస్తున్నాం.",
    notOfficer: "ఈ స్క్రీన్‌లో ప్రత్యక్ష డేటా అధికారులకు మాత్రమే. సేవ్ చేసిన నమూనా చూపిస్తున్నాం.",
    unreachable: "సర్వర్‌ను చేరుకోలేకపోయాం. సేవ్ చేసిన నమూనా చూపిస్తున్నాం.",
    error: "సర్వర్ లోపం చూపింది. సేవ్ చేసిన నమూనా చూపిస్తున్నాం.",
  },
  ur: {
    signIn: "براہِ راست ڈیٹا کے لیے افسر کے طور پر سائن ان کریں۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔",
    rejected: "آپ کا سائن ان قبول نہیں ہوا۔ براہِ راست ڈیٹا کے لیے دوبارہ سائن ان کریں۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔",
    notOfficer: "اس صفحے کا براہِ راست ڈیٹا صرف افسران کے لیے ہے۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔",
    unreachable: "سرور سے رابطہ نہیں ہو سکا۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔",
    error: "سرور نے خرابی بتائی۔ محفوظ شدہ نمونہ دکھایا جا رہا ہے۔",
  },
  hi: {
    signIn: "लाइव डेटा देखने के लिए अधिकारी के रूप में साइन इन करें। सहेजा हुआ स्नैपशॉट दिखाया जा रहा है।",
    rejected: "आपका साइन इन स्वीकार नहीं हुआ। लाइव डेटा के लिए फिर से साइन इन करें। सहेजा हुआ स्नैपशॉट दिखाया जा रहा है।",
    notOfficer: "इस स्क्रीन का लाइव डेटा केवल अधिकारियों के लिए है। सहेजा हुआ स्नैपशॉट दिखाया जा रहा है।",
    unreachable: "सर्वर से संपर्क नहीं हो सका। सहेजा हुआ स्नैपशॉट दिखाया जा रहा है।",
    error: "सर्वर ने त्रुटि बताई। सहेजा हुआ स्नैपशॉट दिखाया जा रहा है।",
  },
} satisfies Record<Locale, Record<LiveReason, string>>;
