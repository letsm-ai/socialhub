import React from "react";
import { useLang } from "@/contexts/LanguageContext";
import { Construction } from "lucide-react";

/**
 * Dashboard Overview - placeholder shown inside DashboardLayout.
 */
export default function Dashboard() {
  const { lang } = useLang();
  return (
    <div data-testid="dashboard-page">
      <div className="mb-8">
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "نظرة عامة" : "Overview"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar" ? "أهلاً بك في لوحة تحكم سوشال هَب." : "Welcome to your SocialHub dashboard."}
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
            ? "ستظهر هنا بيانات اشتراكك، رصيد الرسائل الترويجية، وزر فتح صندوق Chatwoot."
            : "Subscription details, promotional credits balance, and an Open Inbox button will appear here."}
        </p>
      </div>
    </div>
  );
}
