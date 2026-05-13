import React, { createContext, useContext, useEffect, useState } from "react";
import { translations } from "@/i18n/translations";

const LanguageContext = createContext({
  lang: "ar",
  dir: "rtl",
  t: (k) => k,
  toggleLang: () => {},
});

export const LanguageProvider = ({ children }) => {
  const [lang, setLang] = useState("ar");
  const dir = lang === "ar" ? "rtl" : "ltr";

  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = dir;
  }, [lang, dir]);

  const t = (key) => {
    const parts = key.split(".");
    let val = translations[lang];
    for (const p of parts) {
      if (val == null) return key;
      val = val[p];
    }
    return val ?? key;
  };

  const toggleLang = () => setLang((l) => (l === "ar" ? "en" : "ar"));

  return (
    <LanguageContext.Provider value={{ lang, dir, t, toggleLang }}>
      {children}
    </LanguageContext.Provider>
  );
};

export const useLang = () => useContext(LanguageContext);
