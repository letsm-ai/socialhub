import React from "react";
import { Outlet, Link, useLocation, useNavigate } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { useLang } from "@/contexts/LanguageContext";
import { useAuth } from "@/contexts/AuthContext";
import { Globe, ShieldCheck, BarChart3, Users, Wallet, Activity, LogOut } from "lucide-react";

/**
 * AdminLayout - layout for the SaaS owner's super-admin area (/admin/*).
 * Same shell pattern as DashboardLayout but visually distinguished (charcoal sidebar).
 */
export default function AdminLayout() {
  const { t, lang, toggleLang } = useLang();
  const { logout } = useAuth();
  const loc = useLocation();
  const navigate = useNavigate();

  const onLogout = async () => {
    await logout();
    navigate("/login", { replace: true });
  };

  const navItems = [
    { to: "/admin", label: lang === "ar" ? "نظرة عامة" : "Overview", icon: BarChart3, testId: "admin-side-overview" },
    { to: "/admin/clients", label: lang === "ar" ? "العملاء" : "Clients", icon: Users, testId: "admin-side-clients" },
    { to: "/admin/billing", label: lang === "ar" ? "الفوترة" : "Billing", icon: Wallet, testId: "admin-side-billing" },
    { to: "/admin/quotas", label: lang === "ar" ? "حصص الرسائل" : "Quotas", icon: Activity, testId: "admin-side-quotas" },
  ];

  return (
    <div className="min-h-screen bg-stone-50" data-testid="admin-layout">
      <header className="h-16 bg-stone-900 text-stone-100 border-b border-stone-800 px-4 lg:px-6 flex items-center justify-between sticky top-0 z-40">
        <div className="flex items-center gap-4">
          <Link to="/" data-testid="admin-logo-link" className="[&_span]:!text-white">
            <Logo size="small" />
          </Link>
          <span className="hidden md:inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-amber-400">
            <ShieldCheck size={12} />
            {lang === "ar" ? "لوحة المشرف" : "Super Admin"}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={toggleLang}
            data-testid="admin-lang-toggle"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-200 hover:text-amber-400 rounded-lg hover:bg-stone-800"
          >
            <Globe size={16} />
            <span>{t("nav.langLabel")}</span>
          </button>
          <button
            data-testid="admin-logout"
            onClick={onLogout}
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-200 hover:text-red-400 rounded-lg hover:bg-stone-800"
          >
            <LogOut size={16} />
            <span className="hidden sm:inline">{lang === "ar" ? "خروج" : "Log out"}</span>
          </button>
        </div>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-[240px_1fr]">
        <aside className="hidden md:block bg-stone-900 text-stone-200 min-h-[calc(100vh-4rem)] p-4" data-testid="admin-sidebar">
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
                      ? "bg-emerald-700 text-white"
                      : "text-stone-300 hover:bg-stone-800 hover:text-white"
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
