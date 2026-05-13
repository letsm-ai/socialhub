import React from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLang } from "@/contexts/LanguageContext";
import { Link } from "react-router-dom";

export const CTA = () => {
  const { t, lang } = useLang();
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;

  return (
    <section className="py-20 md:py-28" data-testid="cta-section">
      <div className="max-w-6xl mx-auto px-6">
        <div className="relative overflow-hidden rounded-[2rem] bg-emerald-900 px-8 py-16 md:px-16 md:py-20 text-center">
          {/* Background decorations */}
          <div className="absolute inset-0 bg-grid-pattern opacity-10"></div>
          <div className="absolute -top-32 -end-32 w-96 h-96 bg-emerald-700 rounded-full blur-3xl opacity-50"></div>
          <div className="absolute -bottom-32 -start-32 w-96 h-96 bg-amber-500/20 rounded-full blur-3xl"></div>

          <div className="relative">
            <h2 className="font-heading text-3xl md:text-5xl font-bold text-white mb-5 leading-tight max-w-3xl mx-auto">
              {t("cta.title")}
            </h2>
            <p className="text-emerald-100/80 text-lg max-w-2xl mx-auto mb-10">
              {t("cta.subtitle")}
            </p>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/register">
                <Button
                  data-testid="cta-primary"
                  size="lg"
                  className="bg-amber-500 hover:bg-amber-400 text-stone-900 rounded-2xl px-8 h-14 text-base font-bold shadow-lg shadow-amber-900/30 hover:-translate-y-1 transition-all"
                >
                  {t("cta.primary")}
                  <Arrow className="ms-2" size={18} />
                </Button>
              </Link>
              <Button
                data-testid="cta-secondary"
                size="lg"
                variant="outline"
                className="rounded-2xl px-8 h-14 text-base font-semibold border-2 border-white/30 bg-white/10 backdrop-blur text-white hover:bg-white/20 hover:border-white/60"
              >
                {t("cta.secondary")}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
