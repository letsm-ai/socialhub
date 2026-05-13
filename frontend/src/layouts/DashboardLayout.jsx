import React from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { useLang } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";
import { Globe, LayoutDashboard, CreditCard, Wallet, Plug, MessageSquare, Settings, LogOut, ExternalLink } from "lucide-react";

/**
 * DashboardLayout - layout for the authenticated client area (/dashboard/*).
 * Includes a sidebar with primary nav and a top bar.
 * Sidebar items are placeholders – wired in next phase.
 */
export default function DashboardLayout() {
  const { t, lang, toggleLang } = useLang();
  const { user, logout } = useAuth();
  const loc = useLocation();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const navItems = [
    { to: "/dashboard", label: lang === "ar" ? "نظرة عامة" : "Overview", icon: LayoutDashboard, testId: "side-overview" },
    { to: "/dashboard/channels", label: lang === "ar" ? "القنوات" : "Channels", icon: Plug, testId: "side-channels" },
    { to: "/dashboard/billing", label: lang === "ar" ? "الفوترة" : "Billing", icon: CreditCard, testId: "side-billing" },
    { to: "/dashboard/wallet", label: lang === "ar" ? "المحفظة" : "Wallet", icon: Wallet, testId: "side-wallet" },
    { to: "/dashboard/settings", label: lang === "ar" ? "الإعدادات" : "Settings", icon: Settings, testId: "side-settings" },
  ];

  // Chatwoot URL - the "Inbox" sidebar item opens external Chatwoot directly
  const chatwootUrl = process.env.REACT_APP_CHATWOOT_URL || "https://chat.socialhub.om";

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
            onClick={onLogout}
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
            {/* Chatwoot Inbox - external link */}
            <a
              href={chatwootUrl}
              target="_blank"
              rel="noopener noreferrer"
              data-testid="side-inbox-external"
              className="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium text-stone-700 hover:bg-stone-100 transition-colors"
            >
              <MessageSquare size={18} />
              <span className="flex-1">{lang === "ar" ? "صندوق Chatwoot" : "Chatwoot Inbox"}</span>
              <ExternalLink size={12} className="text-stone-400" />
            </a>
          </nav>
        </aside>

        <main className="px-4 lg:px-8 py-6 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
