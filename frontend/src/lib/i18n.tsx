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
  "Identity duplicates": "पहचान दोहराव",
  "Shared-contact clusters": "साझा संपर्क समूह",
  "Rules in force": "लागू नियम",
  "Degree & certificate feed": "डिग्री व प्रमाण-पत्र फ़ीड",
  "Sign in as a demo user": "डेमो उपयोगकर्ता के रूप में साइन इन करें",
  "One student. One APAAR ID.": "एक छात्र। एक APAAR ID।",
  "One verifiable record.": "एक सत्यापन योग्य रिकॉर्ड।",
  "AICTE officer": "AICTE अधिकारी",
  "Institution admin": "संस्थान व्यवस्थापक",
  "University registrar": "विश्वविद्यालय कुलसचिव",
  "State regulator (DTE)": "राज्य नियामक (DTE)",
  "Employer / verifier": "नियोक्ता / सत्यापनकर्ता",
  "Student": "छात्र",
  "Auditor": "लेखा परीक्षक",
  "Institution upload": "संस्थान अपलोड",
  "APAAR validation": "APAAR सत्यापन",
  "Data verification": "डेटा जाँच",
  "Central repository": "केंद्रीय भंडार",
  "Analytics & monitoring": "विश्लेषण व निगरानी",
  "Authorised verification": "अधिकृत सत्यापन",
  "State-wise monitoring": "राज्यवार निगरानी",
  "Highest-risk institutions": "सर्वाधिक जोखिम वाले संस्थान",
  "Run national scan": "राष्ट्रीय स्कैन चलाएँ",
  "Verify chain": "श्रृंखला जाँचें",
  "Approve": "स्वीकृत करें",
  "Deny": "अस्वीकार करें",
  "Consent requests": "सहमति अनुरोध",
  "Who has accessed my data": "मेरा डेटा किसने देखा",
  "Record exit": "निकास दर्ज करें",
  "Choose file": "फ़ाइल चुनें",
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
