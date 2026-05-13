import React from "react";
import ComingSoon from "@/pages/ComingSoon";
import { useLang } from "@/contexts/LanguageContext";

export default function AdminDashboard() {
  const { lang } = useLang();
  return (
    <ComingSoon
      testId="admin-page"
      title={lang === "ar" ? "لوحة تحكم المشرف" : "Admin Dashboard"}
      description={
        lang === "ar"
          ? "لوحة المشرف قيد التطوير. ستعرض MRR، قائمة العملاء، إدارة الحصص، وحالة مزامنة Chatwoot."
          : "Admin dashboard is under development. It will show MRR, client list, quota management, and Chatwoot sync status."
      }
    />
  );
}
