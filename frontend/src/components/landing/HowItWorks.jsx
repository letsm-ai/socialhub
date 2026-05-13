import React from "react";
import { useLang } from "@/contexts/LanguageContext";
import { UserPlus, Link2, MessageSquareHeart } from "lucide-react";

export const HowItWorks = () => {
  const { t } = useLang();
  const steps = [
    { n: t("how.steps.s1.n"), title: t("how.steps.s1.title"), desc: t("how.steps.s1.desc"), icon: UserPlus },
    { n: t("how.steps.s2.n"), title: t("how.steps.s2.title"), desc: t("how.steps.s2.desc"), icon: Link2 },
    { n: t("how.steps.s3.n"), title: t("how.steps.s3.title"), desc: t("how.steps.s3.desc"), icon: MessageSquareHeart },
  ];

  return (
    <section id="how" className="py-24 md:py-32 bg-stone-50/60 border-y border-stone-200/70" data-testid="how-section">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="max-w-2xl mb-16 text-center mx-auto">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-emerald-700 mb-3">
            {t("how.overline")}
          </p>
          <h2 className="font-heading text-3xl md:text-5xl font-bold text-stone-900 mb-5 leading-tight">
            {t("how.title")}
          </h2>
          <p className="text-lg text-stone-600">{t("how.subtitle")}</p>
        </div>

        <div className="relative grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* Connecting line */}
          <div className="hidden md:block absolute top-12 start-[16.66%] end-[16.66%] h-px bg-gradient-to-r from-transparent via-emerald-300 to-transparent"></div>

          {steps.map((s, i) => (
            <div key={i} className="relative text-center" data-testid={`how-step-${i + 1}`}>
              <div className="relative inline-flex">
                <div className="absolute inset-0 bg-emerald-200 rounded-3xl blur-xl opacity-50"></div>
                <div className="relative w-24 h-24 mx-auto rounded-3xl bg-white border-2 border-emerald-100 shadow-sm flex items-center justify-center">
                  <s.icon size={32} className="text-emerald-800" strokeWidth={1.8} />
                </div>
                <div className="absolute -top-3 -end-3 w-10 h-10 rounded-full bg-amber-500 border-4 border-stone-50 flex items-center justify-center font-heading font-bold text-white text-lg">
                  {s.n}
                </div>
              </div>

              <h3 className="font-heading text-xl md:text-2xl font-bold text-stone-900 mt-6 mb-3">
                {s.title}
              </h3>
              <p className="text-stone-600 leading-relaxed max-w-sm mx-auto">{s.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
