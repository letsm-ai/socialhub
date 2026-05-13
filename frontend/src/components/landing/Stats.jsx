import React from "react";
import { useLang } from "@/contexts/LanguageContext";
import { TrendingUp, Zap, MessageSquare, ShieldCheck } from "lucide-react";

export const Stats = () => {
  const { t } = useLang();
  const items = [
    { v: t("stats.response_v"), l: t("stats.response"), icon: Zap },
    { v: t("stats.sales_v"), l: t("stats.sales"), icon: TrendingUp },
    { v: t("stats.messages_v"), l: t("stats.messages"), icon: MessageSquare },
    { v: t("stats.uptime_v"), l: t("stats.uptime"), icon: ShieldCheck },
  ];
  return (
    <section className="py-16 md:py-20 border-y border-stone-200/70 bg-stone-50/50" data-testid="stats-section">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-8 md:gap-4">
          {items.map((it, i) => (
            <div key={i} className="flex flex-col items-center text-center" data-testid={`stat-${i}`}>
              <div className="w-12 h-12 rounded-2xl bg-emerald-50 border border-emerald-100 flex items-center justify-center mb-3">
                <it.icon size={22} className="text-emerald-800" />
              </div>
              <div className="font-heading text-3xl md:text-4xl font-bold text-stone-900 text-glow-emerald">
                {it.v}
              </div>
              <div className="text-sm text-stone-600 mt-1">{it.l}</div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
