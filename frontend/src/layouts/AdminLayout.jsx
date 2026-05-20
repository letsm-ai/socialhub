import React from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import MiniSidebar from "@/components/shared/MiniSidebar";
import { useLang } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";
import { BarChart3, Users, Wallet, Activity, LogOut, Globe, ShieldCheck, Bot } from "lucide-react";

/**
 * AdminLayout — dark mini sidebar variant.
 */
export default function AdminLayout() {
  const { t, lang, toggleLang } = useLang();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const loc = useLocation();

  const navItems = [
    { to: "/admin", label: lang === "ar" ? "نظرة عامة" : "Overview", icon: BarChart3, testId: "admin-side-overview" },
    { to: "/admin/clients", label: lang === "ar" ? "العملاء" : "Clients", icon: Users, testId: "admin-side-clients" },
    { to: "/admin/billing", label: lang === "ar" ? "الفوترة" : "Billing", icon: Wallet, testId: "admin-side-billing" },
    { to: "/admin/quotas", label: lang === "ar" ? "حصص الرسائل" : "Quotas", icon: Activity, testId: "admin-side-quotas" },
    { to: "/admin/ai", label: lang === "ar" ? "مساعد AI" : "AI Agent", icon: Bot, testId: "admin-side-ai" },
  ];

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const pageTitle = (() => {
    if (loc.pathname.startsWith("/admin/clients")) return lang === "ar" ? "العملاء" : "Clients";
    if (loc.pathname.startsWith("/admin/billing")) return lang === "ar" ? "الفوترة والإيرادات" : "Billing & Revenue";
    if (loc.pathname.startsWith("/admin/quotas")) return lang === "ar" ? "حصص الرسائل" : "Quotas";
    if (loc.pathname.startsWith("/admin/ai")) return lang === "ar" ? "مساعد AI" : "AI Agent";
    return lang === "ar" ? "نظرة عامة" : "Overview";
  })();

  return (
    <div className="min-h-screen bg-[#FAF8F2] flex" data-testid="admin-layout" dir={lang === "ar" ? "rtl" : "ltr"}>
      <MiniSidebar items={navItems} theme="dark" />

      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 bg-white border-b border-stone-200 px-5 lg:px-8 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <h1 className="font-heading text-base md:text-lg font-bold text-stone-900">{pageTitle}</h1>
            <span className="hidden md:inline-flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-amber-700 ms-2">
              <ShieldCheck size={11} />
              {lang === "ar" ? "لوحة المشرف" : "Super Admin"}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={toggleLang}
                    data-testid="admin-lang-toggle"
                    className="w-10 h-10 rounded-xl text-stone-600 hover:bg-stone-100 hover:text-emerald-800 flex items-center justify-center"
                  >
                    <Globe size={18} />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="bg-stone-900 text-white border-stone-800">
                  {lang === "ar" ? "English" : "العربية"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            <div className="hidden sm:flex items-center gap-2 ps-3 pe-1 py-1 rounded-xl bg-stone-50 border border-stone-200">
              <div className="text-end">
                <div className="text-xs font-semibold text-stone-900 leading-tight">{user?.name || "Admin"}</div>
                <div className="text-[10px] text-stone-500 leading-tight">{user?.email}</div>
              </div>
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-stone-800 to-stone-950 flex items-center justify-center font-heading font-bold text-amber-300 text-sm">
                <ShieldCheck size={16} />
              </div>
            </div>

            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={onLogout}
                    data-testid="admin-logout"
                    className="w-10 h-10 rounded-xl text-stone-600 hover:bg-red-50 hover:text-red-700 flex items-center justify-center"
                  >
                    <LogOut size={18} />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="bg-stone-900 text-white border-stone-800">
                  {lang === "ar" ? "تسجيل الخروج" : "Log out"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </header>

        <main className="flex-1 px-4 lg:px-8 py-6 lg:py-8 max-w-[1400px] w-full mx-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
