import React from "react";
import ComingSoon from "@/components/shared/ComingSoon";
import { useLang } from "@/contexts/LanguageContext";

export default function Register() {
  const { lang } = useLang();
  return (
    <ComingSoon
      testId="register-page"
      title={lang === "ar" ? "إنشاء حساب" : "Create account"}
      description={
        lang === "ar"
          ? "صفحة التسجيل قيد التطوير. سنُفعّلها قريباً مع تكامل Stripe وإنشاء حساب Chatwoot تلقائياً."
          : "Registration page is under development. We'll activate it soon with Stripe integration and automatic Chatwoot account creation."
      }
    />
  );
}
