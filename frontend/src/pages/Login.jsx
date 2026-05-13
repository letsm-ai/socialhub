import React from "react";
import ComingSoon from "@/pages/ComingSoon";
import { useLang } from "@/contexts/LanguageContext";

export default function Login() {
  const { lang } = useLang();
  return (
    <ComingSoon
      testId="login-page"
      title={lang === "ar" ? "تسجيل الدخول" : "Log in"}
      description={
        lang === "ar"
          ? "صفحة تسجيل الدخول قيد التطوير. سيتم تفعيلها في المرحلة التالية مع نظام المصادقة الكامل."
          : "Login page is under development. It will be activated in the next phase along with the full authentication system."
      }
    />
  );
}
