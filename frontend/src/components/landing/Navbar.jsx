import React, { useEffect, useState } from "react";
import { Menu, X, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/Logo";
import { useLang } from "@/contexts/LanguageContext";
import { Link } from "react-router-dom";

export const Navbar = () => {
  const { t, lang, toggleLang } = useLang();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const navLinks = [
    { href: "#features", label: t("nav.features"), id: "nav-features" },
    { href: "#how", label: t("nav.how"), id: "nav-how" },
    { href: "#pricing", label: t("nav.pricing"), id: "nav-pricing" },
    { href: "#faq", label: t("nav.faq"), id: "nav-faq" },
  ];

  return (
    <header
      data-testid="main-navbar"
      className={`fixed top-0 inset-x-0 z-50 transition-all duration-300 ${
        scrolled
          ? "bg-white/80 backdrop-blur-xl border-b border-stone-200/60 shadow-sm"
          : "bg-transparent"
      }`}
    >
      <nav className="max-w-7xl mx-auto px-6 lg:px-12 h-16 md:h-20 flex items-center justify-between">
        <Link to="/" data-testid="nav-logo-link">
          <Logo />
        </Link>

        <div className="hidden lg:flex items-center gap-1">
          {navLinks.map((l) => (
            <a
              key={l.href}
              href={l.href}
              data-testid={l.id}
              className="px-4 py-2 text-sm font-medium text-stone-700 hover:text-emerald-800 transition-colors"
            >
              {l.label}
            </a>
          ))}
        </div>

        <div className="hidden lg:flex items-center gap-2">
          <button
            onClick={toggleLang}
            data-testid="lang-toggle-btn"
            className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-700 hover:text-emerald-800 transition-colors rounded-lg hover:bg-stone-100"
          >
            <Globe size={16} />
            <span>{t("nav.langLabel")}</span>
          </button>
          <Link to="/login" data-testid="nav-login-link">
            <Button variant="ghost" className="text-stone-800 hover:bg-stone-100 hover:text-emerald-800">
              {t("nav.login")}
            </Button>
          </Link>
          <Link to="/register" data-testid="nav-register-link">
            <Button
              className="bg-emerald-800 hover:bg-emerald-900 text-white shadow-sm hover:shadow-md hover:-translate-y-0.5 transition-all rounded-xl px-5"
            >
              {t("nav.cta")}
            </Button>
          </Link>
        </div>

        {/* Mobile */}
        <button
          onClick={() => setOpen(!open)}
          data-testid="mobile-menu-toggle"
          className="lg:hidden p-2 rounded-lg hover:bg-stone-100"
          aria-label="menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

      {open && (
        <div className="lg:hidden bg-white border-t border-stone-200 px-6 py-4 flex flex-col gap-3" data-testid="mobile-menu">
          {navLinks.map((l) => (
            <a
              key={l.href}
              href={l.href}
              onClick={() => setOpen(false)}
              className="py-2 text-stone-700 font-medium"
            >
              {l.label}
            </a>
          ))}
          <div className="flex gap-2 pt-3 border-t border-stone-200">
            <button
              onClick={toggleLang}
              className="flex items-center gap-1.5 px-3 py-2 text-sm font-medium text-stone-700 border border-stone-200 rounded-lg"
            >
              <Globe size={16} />
              <span>{t("nav.langLabel")}</span>
            </button>
            <Link to="/login" className="flex-1">
              <Button variant="outline" className="w-full">{t("nav.login")}</Button>
            </Link>
          </div>
          <Link to="/register">
            <Button className="w-full bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl">
              {t("nav.cta")}
            </Button>
          </Link>
        </div>
      )}
    </header>
  );
};
