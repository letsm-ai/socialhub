import React from "react";
import { Quote, Star } from "lucide-react";
import { useLang } from "@/contexts/LanguageContext";

export const Testimonials = () => {
  const { t } = useLang();
  const items = t("testimonials.items");

  return (
    <section className="py-24 md:py-32 bg-stone-50/60 border-y border-stone-200/70" data-testid="testimonials-section">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="max-w-2xl mb-16 text-center mx-auto">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-emerald-700 mb-3">
            {t("testimonials.overline")}
          </p>
          <h2 className="font-heading text-3xl md:text-5xl font-bold text-stone-900 leading-tight">
            {t("testimonials.title")}
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-6xl mx-auto">
          {Array.isArray(items) &&
            items.map((it, i) => (
              <div
                key={i}
                data-testid={`testimonial-${i}`}
                className="bg-white rounded-3xl border border-stone-200 p-7 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 flex flex-col"
              >
                <div className="flex items-center gap-1 mb-4">
                  {[...Array(5)].map((_, k) => (
                    <Star key={k} size={16} className="fill-amber-400 text-amber-400" />
                  ))}
                </div>
                <Quote size={28} className="text-emerald-200 mb-3 rtl-flip" />
                <p className="text-stone-700 leading-relaxed mb-6 flex-1">{it.quote}</p>
                <div className="flex items-center gap-3 pt-5 border-t border-stone-100">
                  <div className="w-11 h-11 rounded-full bg-gradient-to-br from-emerald-700 to-emerald-900 flex items-center justify-center font-heading font-bold text-white">
                    {it.name?.[0]}
                  </div>
                  <div>
                    <p className="font-semibold text-stone-900 text-sm">{it.name}</p>
                    <p className="text-xs text-stone-500">{it.role}</p>
                  </div>
                </div>
              </div>
            ))}
        </div>
      </div>
    </section>
  );
};
