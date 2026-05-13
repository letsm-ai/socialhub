import React from "react";
import { Check, Sparkles, ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLang } from "@/contexts/LanguageContext";
import { Link } from "react-router-dom";

export const Pricing = () => {
  const { t, lang } = useLang();
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;

  const plans = [
    {
      key: "growth",
      name: t("pricing.plans.growth.name"),
      desc: t("pricing.plans.growth.desc"),
      price: t("pricing.plans.growth.price"),
      features: t("pricing.plans.growth.features"),
      cta: t("pricing.plans.growth.cta"),
      highlighted: false,
    },
    {
      key: "pro",
      name: t("pricing.plans.pro.name"),
      desc: t("pricing.plans.pro.desc"),
      price: t("pricing.plans.pro.price"),
      features: t("pricing.plans.pro.features"),
      cta: t("pricing.plans.pro.cta"),
      highlighted: true,
    },
    {
      key: "enterprise",
      name: t("pricing.plans.enterprise.name"),
      desc: t("pricing.plans.enterprise.desc"),
      price: t("pricing.plans.enterprise.price"),
      features: t("pricing.plans.enterprise.features"),
      cta: t("pricing.plans.enterprise.cta"),
      highlighted: false,
    },
  ];

  return (
    <section id="pricing" className="py-24 md:py-32" data-testid="pricing-section">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="max-w-2xl mb-16 text-center mx-auto">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-emerald-700 mb-3">
            {t("pricing.overline")}
          </p>
          <h2 className="font-heading text-3xl md:text-5xl font-bold text-stone-900 mb-5 leading-tight">
            {t("pricing.title")}
          </h2>
          <p className="text-lg text-stone-600">{t("pricing.subtitle")}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8 max-w-6xl mx-auto">
          {plans.map((p) => (
            <PlanCard key={p.key} plan={p} t={t} lang={lang} Arrow={Arrow} />
          ))}
        </div>

        {/* Credits Add-on */}
        <div
          data-testid="pricing-credits"
          className="mt-12 max-w-4xl mx-auto bg-stone-900 text-white rounded-3xl p-8 md:p-10 flex flex-col md:flex-row items-center gap-6 md:gap-10"
        >
          <div className="flex-shrink-0 w-16 h-16 rounded-2xl bg-amber-500 flex items-center justify-center">
            <Sparkles size={28} className="text-stone-900" />
          </div>
          <div className="flex-1 text-center md:text-start">
            <h3 className="font-heading text-xl md:text-2xl font-bold mb-2">{t("pricing.credits.title")}</h3>
            <p className="text-stone-300 leading-relaxed">{t("pricing.credits.desc")}</p>
          </div>
          <Button
            data-testid="credits-cta"
            className="bg-amber-500 hover:bg-amber-400 text-stone-900 rounded-xl px-6 h-12 font-semibold whitespace-nowrap"
          >
            {t("pricing.credits.cta")}
          </Button>
        </div>
      </div>
    </section>
  );
};

const PlanCard = ({ plan, t, lang, Arrow }) => {
  const highlighted = plan.highlighted;
  return (
    <div
      data-testid={`plan-${plan.key}`}
      className={`relative rounded-3xl p-8 transition-all duration-300 hover:-translate-y-2 ${
        highlighted
          ? "bg-emerald-900 text-white shadow-2xl shadow-emerald-900/30 border-2 border-emerald-700 md:-mt-4"
          : "bg-white border border-stone-200 hover:shadow-xl hover:border-emerald-200"
      }`}
    >
      {highlighted && (
        <div className="absolute -top-4 inset-x-0 flex justify-center">
          <div className="bg-amber-500 text-stone-900 text-xs font-bold px-4 py-1.5 rounded-full shadow-md flex items-center gap-1.5">
            <Sparkles size={12} />
            {t("pricing.mostPopular")}
          </div>
        </div>
      )}

      <div className="mb-6">
        <h3 className={`font-heading text-2xl font-bold mb-1 ${highlighted ? "text-white" : "text-stone-900"}`}>
          {plan.name}
        </h3>
        <p className={`text-sm ${highlighted ? "text-emerald-100/80" : "text-stone-500"}`}>{plan.desc}</p>
      </div>

      <div className="mb-8 flex items-baseline gap-2">
        <span className={`font-heading text-5xl font-bold ${highlighted ? "text-white" : "text-stone-900"}`}>
          {plan.price}
        </span>
        <div className="flex flex-col">
          <span className={`text-sm font-semibold ${highlighted ? "text-emerald-100" : "text-stone-700"}`}>
            {t("pricing.currency")}
          </span>
          <span className={`text-xs ${highlighted ? "text-emerald-200/70" : "text-stone-500"}`}>
            {t("pricing.monthly")}
          </span>
        </div>
      </div>

      <Link to="/register">
        <Button
          data-testid={`plan-${plan.key}-cta`}
          className={`w-full h-12 rounded-xl font-semibold mb-8 ${
            highlighted
              ? "bg-amber-500 hover:bg-amber-400 text-stone-900"
              : "bg-stone-900 hover:bg-emerald-900 text-white"
          }`}
        >
          {plan.cta}
          <Arrow className="ms-2" size={16} />
        </Button>
      </Link>

      <ul className="space-y-3">
        {plan.features.map((f, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <div
              className={`flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center mt-0.5 ${
                highlighted ? "bg-emerald-700" : "bg-emerald-50"
              }`}
            >
              <Check size={12} className={highlighted ? "text-amber-300" : "text-emerald-700"} strokeWidth={3} />
            </div>
            <span className={`text-sm ${highlighted ? "text-emerald-50" : "text-stone-700"}`}>{f}</span>
          </li>
        ))}
      </ul>
    </div>
  );
};
