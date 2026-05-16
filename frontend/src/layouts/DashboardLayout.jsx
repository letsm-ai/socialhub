import React from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import MiniSidebar from "@/components/shared/MiniSidebar";
import { useLang } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";
import {
  Tooltip, TooltipContent, TooltipProvider, TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  LayoutDashboard, Plug, CreditCard, Wallet, LogOut, Globe,
} from "lucide-react";

/**
 * DashboardLayout — respond.io-style mini icon sidebar.
 */
export default function DashboardLayout() {
  const { t, lang, toggleLang } = useLang();
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const loc = useLocation();

  const navItems = [
    { to: "/dashboard", label: lang === "ar" ? "نظرة عامة" : "Overview", icon: LayoutDashboard, testId: "side-overview" },
    { to: "/dashboard/channels", label: lang === "ar" ? "القنوات" : "Channels", icon: Plug, testId: "side-channels" },
    { to: "/dashboard/billing", label: lang === "ar" ? "الفوترة" : "Billing", icon: CreditCard, testId: "side-billing" },
    { to: "/dashboard/wallet", label: lang === "ar" ? "المحفظة" : "Wallet", icon: Wallet, testId: "side-wallet" },
  ];

  const bottomItems = [];

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const pageTitle = (() => {
    if (loc.pathname.startsWith("/dashboard/billing")) return lang === "ar" ? "الفوترة" : "Billing";
    if (loc.pathname.startsWith("/dashboard/wallet")) return lang === "ar" ? "المحفظة" : "Wallet";
    if (loc.pathname.startsWith("/dashboard/channels")) return lang === "ar" ? "القنوات" : "Channels";
    return lang === "ar" ? "نظرة عامة" : "Overview";
  })();

  return (
    <div className="min-h-screen bg-[#FAF8F2] flex" data-testid="dashboard-layout" dir={lang === "ar" ? "rtl" : "ltr"}>
      <MiniSidebar items={navItems} bottomItems={bottomItems} theme="light" />

      <div className="flex-1 flex flex-col min-w-0">
        {/* Top bar */}
        <header className="h-16 bg-white border-b border-stone-200 px-5 lg:px-8 flex items-center justify-between sticky top-0 z-30">
          <div className="flex items-center gap-3">
            <h1 className="font-heading text-base md:text-lg font-bold text-stone-900">{pageTitle}</h1>
            {user?.company_name && (
              <span
                data-testid="dashboard-company-badge"
                className="hidden md:inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-900 bg-emerald-50 border border-emerald-200 rounded-full px-2.5 py-1 ms-2"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>
                {user.company_name}
              </span>
            )}
          </div>

          <div className="flex items-center gap-2">
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={toggleLang}
                    data-testid="dashboard-lang-toggle"
                    className="w-10 h-10 rounded-xl text-stone-600 hover:bg-stone-100 hover:text-emerald-800 flex items-center justify-center"
                    aria-label="language"
                  >
                    <Globe size={18} />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="bottom" className="bg-stone-900 text-white border-stone-800">
                  {lang === "ar" ? "English" : "العربية"}
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>

            {/* User chip */}
            <div className="hidden sm:flex items-center gap-2 ps-3 pe-1 py-1 rounded-xl bg-stone-50 border border-stone-200">
              <div className="text-end">
                <div className="text-xs font-semibold text-stone-900 leading-tight">{user?.name || "—"}</div>
                <div className="text-[10px] text-stone-500 leading-tight">{user?.email}</div>
              </div>
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-700 to-emerald-900 flex items-center justify-center font-heading font-bold text-white text-sm">
                {user?.name?.[0]?.toUpperCase() || "?"}
              </div>
            </div>

            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    onClick={onLogout}
                    data-testid="dashboard-logout"
                    className="w-10 h-10 rounded-xl text-stone-600 hover:bg-red-50 hover:text-red-700 flex items-center justify-center"
                    aria-label="logout"
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
