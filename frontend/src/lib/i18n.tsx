import { createContext, useContext, useState, type ReactNode } from "react";

type Lang = "en" | "hi";

const HI: Record<string, string> = {
  "National overview": "राष्ट्रीय अवलोकन",
  "Institutions": "संस्थान",
  "Review queue": "समीक्षा कतार",
  "Reports": "रिपोर्ट",
  "Audit trail": "ऑडिट ट्रेल",
  "Overview": "अवलोकन",
  "Upload students": "छात्र डेटा अपलोड",
  "Student records": "छात्र रिकॉर्ड",
  "Integration API": "एकीकरण API",
  "Verify credential": "प्रमाण-पत्र सत्यापन",
  "My record": "मेरा रिकॉर्ड",
  "Sign out": "साइन आउट",
  "Live": "लाइव",
  "Approved intake": "स्वीकृत प्रवेश क्षमता",
  "Enrolled": "नामांकित",
  "APAAR coverage": "APAAR कवरेज",
  "Open review items": "खुले समीक्षा मामले",
  "High-risk institutions": "उच्च जोखिम संस्थान",
  "Excess admissions": "अतिरिक्त प्रवेश",
  "Dual enrolments": "दोहरा नामांकन",
};

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (s: string) => string }>({
  lang: "en", setLang: () => {}, t: (s) => s,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try { return (localStorage.getItem("vp_lang") as Lang) || "en"; } catch { return "en"; }
  });
  const setLang = (l: Lang) => {
    setLangState(l);
    try { localStorage.setItem("vp_lang", l); } catch { /* ignore */ }
  };
  const t = (s: string) => (lang === "hi" ? HI[s] ?? s : s);
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);
