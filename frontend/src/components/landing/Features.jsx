import React from "react";
import { Inbox, Bot, MessageCircle, Users, UserCheck, Sparkles, Zap, BarChart3 } from "lucide-react";
import { useLang } from "@/contexts/LanguageContext";

export const Features = () => {
  const { t, lang } = useLang();

  return (
    <section id="features" className="py-24 md:py-32" data-testid="features-section">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        {/* Header */}
        <div className="max-w-2xl mb-16">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-emerald-700 mb-3" data-testid="features-overline">
            {t("features.overline")}
          </p>
          <h2 className="font-heading text-3xl md:text-5xl font-bold text-stone-900 mb-5 leading-tight" data-testid="features-title">
            {t("features.title")}
          </h2>
          <p className="text-lg text-stone-600" data-testid="features-subtitle">
            {t("features.subtitle")}
          </p>
        </div>

        {/* Bento grid */}
        <div className="grid grid-cols-1 md:grid-cols-6 gap-5">
          {/* Inbox - large */}
          <BentoCard
            className="md:col-span-4 md:row-span-2 bg-emerald-900 text-white border-emerald-900"
            tag={t("features.items.inbox.tag")}
            tagColor="emerald-light"
            title={t("features.items.inbox.title")}
            desc={t("features.items.inbox.desc")}
            dark
            testId="feature-inbox"
          >
            <ChannelsVisual />
          </BentoCard>

          {/* AI */}
          <BentoCard
            className="md:col-span-2 bg-amber-50/60 border-amber-200/60"
            tag={t("features.items.ai.tag")}
            tagColor="amber"
            title={t("features.items.ai.title")}
            desc={t("features.items.ai.desc")}
            testId="feature-ai"
            icon={Bot}
            iconBg="bg-amber-600"
          />

          {/* WhatsApp */}
          <BentoCard
            className="md:col-span-2 bg-white border-stone-200"
            tag={t("features.items.whatsapp.tag")}
            tagColor="emerald"
            title={t("features.items.whatsapp.title")}
            desc={t("features.items.whatsapp.desc")}
            testId="feature-whatsapp"
            icon={MessageCircle}
            iconBg="bg-emerald-700"
          />

          {/* Team */}
          <BentoCard
            className="md:col-span-3 bg-white border-stone-200"
            tag={t("features.items.team.tag")}
            tagColor="emerald"
            title={t("features.items.team.title")}
            desc={t("features.items.team.desc")}
            testId="feature-team"
            icon={Users}
            iconBg="bg-stone-800"
          />

          {/* CRM */}
          <BentoCard
            className="md:col-span-3 bg-white border-stone-200"
            tag={t("features.items.crm.tag")}
            tagColor="emerald"
            title={t("features.items.crm.title")}
            desc={t("features.items.crm.desc")}
            testId="feature-crm"
            icon={UserCheck}
            iconBg="bg-emerald-800"
          />
        </div>
      </div>
    </section>
  );
};

const BentoCard = ({ className = "", tag, tagColor, title, desc, dark = false, children, icon: Icon, iconBg, testId }) => {
  const tagColors = {
    emerald: "bg-emerald-50 text-emerald-800 border-emerald-100",
    "emerald-light": "bg-emerald-700/30 text-emerald-100 border-emerald-600/30",
    amber: "bg-amber-100 text-amber-800 border-amber-200",
  };
  return (
    <div
      data-testid={testId}
      className={`relative rounded-3xl border p-6 md:p-8 transition-all duration-300 hover:shadow-xl hover:-translate-y-1 overflow-hidden ${className}`}
    >
      <div className="flex items-center justify-between mb-4">
        <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full border ${tagColors[tagColor]}`}>
          {tag}
        </span>
        {Icon && (
          <div className={`w-11 h-11 rounded-2xl ${iconBg} flex items-center justify-center shadow-md`}>
            <Icon size={20} className="text-white" />
          </div>
        )}
      </div>
      <h3 className={`font-heading text-xl md:text-2xl font-bold mb-3 leading-tight ${dark ? "text-white" : "text-stone-900"}`}>
        {title}
      </h3>
      <p className={`text-sm md:text-base leading-relaxed ${dark ? "text-emerald-100/80" : "text-stone-600"}`}>
        {desc}
      </p>
      {children && <div className="mt-6">{children}</div>}
    </div>
  );
};

const ChannelsVisual = () => {
  const { lang } = useLang();
  const channels = [
    { name: lang === "ar" ? "واتساب" : "WhatsApp", color: "bg-emerald-500", icon: "💬" },
    { name: lang === "ar" ? "انستقرام" : "Instagram", color: "bg-gradient-to-tr from-pink-500 to-amber-500", icon: "📷" },
    { name: lang === "ar" ? "فيسبوك" : "Facebook", color: "bg-blue-600", icon: "f" },
    { name: lang === "ar" ? "البريد" : "Email", color: "bg-amber-600", icon: "✉" },
    { name: lang === "ar" ? "ويب شات" : "Web Chat", color: "bg-stone-700", icon: "🌐" },
  ];
  return (
    <div className="relative flex flex-wrap gap-3 items-center">
      {channels.map((c, i) => (
        <div
          key={i}
          className="flex items-center gap-2 bg-white/10 backdrop-blur-md border border-white/20 rounded-2xl px-4 py-2.5 hover:bg-white/20 transition-colors"
        >
          <div className={`w-7 h-7 rounded-lg ${c.color} flex items-center justify-center text-sm font-bold text-white`}>
            {c.icon}
          </div>
          <span className="text-sm font-medium text-emerald-50">{c.name}</span>
        </div>
      ))}
      <div className="ms-2 flex items-center gap-1.5 px-3 py-1.5 bg-amber-400 rounded-full">
        <Sparkles size={12} className="text-amber-900" />
        <span className="text-[11px] font-bold text-amber-900">
          {lang === "ar" ? "كلها في شاشة واحدة" : "All in one screen"}
        </span>
      </div>
    </div>
  );
};
