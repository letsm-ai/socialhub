import React from "react";
import { Outlet, Link } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { useLang } from "@/contexts/LanguageContext";
import { Globe } from "lucide-react";

/**
 * AuthLayout - minimal layout for /login and /register pages.
 * Centers content, shows logo + language toggle in a thin top bar.
 */
export default function AuthLayout() {
  const { t, toggleLang } = useLang();
  return (
    <div className="min-h-screen bg-[#FDFBF7]" data-testid="auth-layout">
      <header className="h-16 px-6 lg:px-12 flex items-center justify-between border-b border-stone-200/60">
        <Link to="/" data-testid="auth-logo-link">
          <Logo size="small" />
        </Link>
        <button
          onClick={toggleLang}
          data-testid="auth-lang-toggle"
          className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-700 hover:text-emerald-800 rounded-lg hover:bg-stone-100"
        >
          <Globe size={16} />
          <span>{t("nav.langLabel")}</span>
        </button>
      </header>
      <main className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-6 py-12">
        <Outlet />
      </main>
    </div>
  );
}
