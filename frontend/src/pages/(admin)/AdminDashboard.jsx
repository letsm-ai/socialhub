import React from "react";
import { useLang } from "@/contexts/LanguageContext";
import { Construction } from "lucide-react";

/**
 * Admin Overview - placeholder shown inside AdminLayout.
 */
export default function AdminDashboard() {
  const { lang } = useLang();
  return (
    <div data-testid="admin-page">
      <div className="mb-8">
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "نظرة عامة على المنصة" : "Platform Overview"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar"
            ? "إدارة العملاء، الفوترة، وحصص الرسائل عبر سوشال هَب."
            : "Manage clients, billing, and message quotas across SocialHub."}
        </p>
      </div>
      <div className="bg-white border border-stone-200 rounded-2xl p-10 text-center">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-100 flex items-center justify-center mb-4">
          <Construction size={24} className="text-amber-700" />
        </div>
        <h2 className="font-heading text-xl font-bold text-stone-900 mb-2">
          {lang === "ar" ? "قريباً..." : "Coming soon..."}
        </h2>
        <p className="text-stone-600 max-w-md mx-auto">
          {lang === "ar"
            ? "ستظهر هنا إحصائيات MRR، قائمة العملاء، إدارة الحصص، وحالة مزامنة Chatwoot."
            : "MRR analytics, client list, quota management, and Chatwoot sync status will appear here."}
        </p>
      </div>
    </div>
  );
}
