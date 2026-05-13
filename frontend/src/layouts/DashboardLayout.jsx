import React from "react";
import { Outlet, Link, useLocation } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { useLang } from "@/contexts/LanguageContext";
import { Globe, LayoutDashboard, CreditCard, MessageSquare, Settings, LogOut } from "lucide-react";

/**
 * DashboardLayout - layout for the authenticated client area (/dashboard/*).
 * Includes a sidebar with primary nav and a top bar.
 * Sidebar items are placeholders – wired in next phase.
 */
export default function DashboardLayout() {
  const { t, lang, toggleLang } = useLang();
  const loc = useLocation();

  const navItems = [
    { to: "/dashboard", label: lang === "ar" ? "نظرة عامة" : "Overview", icon: LayoutDashboard, testId: "side-overview" },
    { to: "/dashboard/billing", label: lang === "ar" ? "الفوترة" : "Billing", icon: CreditCard, testId: "side-billing" },
    { to: "/dashboard/inbox", label: lang === "ar" ? "صندوق الرسائل" : "Inbox", icon: MessageSquare, testId: "side-inbox" },
    { to: "/dashboard/settings", label: lang === "ar" ? "الإعدادات" : "Settings", icon: Settings, testId: "side-settings" },
  ];

  return (
    <div className="min-h-screen bg-[#FDFBF7]" data-testid="dashboard-layout">
      {/* Top bar */}
      <header className="h-16 bg-white border-b border-stone-200 px-4 lg:px-6 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-4">
          <Link to="/" data-testid="dashboard-logo-link">
            <Logo size="small" />
          </Link>
          <span className="hidden md:inline-block text-xs font-semibold uppercase tracking-wider text-stone-400">
            {lang === "ar" ? "لوحة التحكم" : "Dashboard"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleLang}
            data-testid="dashboard-lang-toggle"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-700 hover:text-emerald-800 rounded-lg hover:bg-stone-100"
          >
            <Globe size={16} />
            <span>{t("nav.langLabel")}</span>
          </button>
          <button
            data-testid="dashboard-logout"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-700 hover:text-red-700 rounded-lg hover:bg-red-50"
          >
            <LogOut size={16} />
            <span className="hidden sm:inline">{lang === "ar" ? "خروج" : "Log out"}</span>
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-[240px_1fr]">
        {/* Sidebar */}
        <aside className="hidden md:block bg-white border-e border-stone-200 min-h-[calc(100vh-4rem)] p-4" data-testid="dashboard-sidebar">
          <nav className="space-y-1">
            {navItems.map((it) => {
              const active = loc.pathname === it.to;
              return (
                <Link
                  key={it.to}
                  to={it.to}
                  data-testid={it.testId}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${
                    active
                      ? "bg-emerald-50 text-emerald-800 border border-emerald-100"
                      : "text-stone-700 hover:bg-stone-100"
                  }`}
                >
                  <it.icon size={18} strokeWidth={active ? 2.5 : 2} />
                  <span>{it.label}</span>
                </Link>
              );
            })}
          </nav>
        </aside>

        <main className="px-4 lg:px-8 py-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
