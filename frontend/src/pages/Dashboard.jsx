import React from "react";
import ComingSoon from "@/pages/ComingSoon";
import { useLang } from "@/contexts/LanguageContext";

export default function Dashboard() {
  const { lang } = useLang();
  return (
    <ComingSoon
      testId="dashboard-page"
      title={lang === "ar" ? "لوحة تحكم العميل" : "Client Dashboard"}
      description={
        lang === "ar"
          ? "لوحة تحكم العميل قيد التطوير. ستعرض الاشتراك الحالي، رصيد الرسائل، وزر فتح Chatwoot Inbox."
          : "Client dashboard is under development. It will show current subscription, message credits, and an Open Inbox button to Chatwoot."
      }
    />
  );
}
