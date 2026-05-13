import React from "react";
import { ArrowLeft, ArrowRight, Play, MessageCircle, Instagram, Facebook, Mail, Bot, CheckCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useLang } from "@/contexts/LanguageContext";

export const Hero = () => {
  const { t, lang } = useLang();
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;

  return (
    <section className="relative pt-32 pb-20 md:pt-40 md:pb-32 overflow-hidden" data-testid="hero-section">
      {/* Background layers */}
      <div className="absolute inset-0 bg-grid-pattern opacity-50"></div>
      <div className="absolute inset-0 bg-spotlight"></div>
      <div className="absolute -top-24 -end-24 w-96 h-96 bg-emerald-200/30 rounded-full blur-3xl"></div>
      <div className="absolute top-40 -start-24 w-72 h-72 bg-amber-200/30 rounded-full blur-3xl"></div>

      <div className="relative max-w-7xl mx-auto px-6 lg:px-12">
        {/* Badge */}
        <div className="flex justify-center mb-8 fade-up">
          <div
            data-testid="hero-badge"
            className="inline-flex items-center gap-2 bg-white/80 backdrop-blur-md border border-emerald-100 rounded-full px-4 py-1.5 text-xs font-semibold text-emerald-800 shadow-sm"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-600"></span>
            </span>
            {t("hero.badge")}
          </div>
        </div>

        {/* Headline */}
        <h1
          data-testid="hero-title"
          className="font-heading text-center text-3xl sm:text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight text-stone-900 mb-6 fade-up"
          style={{ animationDelay: "0.1s", lineHeight: 1.6 }}
        >
          <span className="block">{t("hero.title_a")} {t("hero.title_b")}</span>
          <span className="block bg-gradient-to-l from-emerald-700 via-emerald-800 to-emerald-900 bg-clip-text text-transparent pb-2">
            {t("hero.title_c")}
          </span>
        </h1>

        {/* Subtitle */}
        <p
          data-testid="hero-subtitle"
          className="max-w-3xl mx-auto text-center text-lg md:text-xl text-stone-600 leading-relaxed mb-10 fade-up"
          style={{ animationDelay: "0.2s" }}
        >
          {t("hero.subtitle")}
        </p>

        {/* CTAs */}
        <div
          className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-6 fade-up"
          style={{ animationDelay: "0.3s" }}
        >
          <Button
            data-testid="hero-cta-primary"
            size="lg"
            className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-2xl px-8 h-14 text-base font-semibold shadow-lg shadow-emerald-900/20 hover:shadow-xl hover:-translate-y-1 transition-all"
          >
            {t("hero.cta_primary")}
            <Arrow className="ms-2" size={18} />
          </Button>
          <Button
            data-testid="hero-cta-secondary"
            size="lg"
            variant="outline"
            className="rounded-2xl px-8 h-14 text-base font-semibold border-2 border-stone-300 hover:bg-white hover:border-emerald-800 transition-all"
          >
            <Play size={16} className="me-2 text-emerald-800" fill="currentColor" />
            {t("hero.cta_secondary")}
          </Button>
        </div>

        <p
          data-testid="hero-trust"
          className="text-center text-sm text-stone-500 fade-up"
          style={{ animationDelay: "0.4s" }}
        >
          {t("hero.trust")}
        </p>

        {/* Dashboard Mock */}
        <div
          className="mt-16 md:mt-24 fade-up"
          style={{ animationDelay: "0.5s" }}
          data-testid="hero-dashboard-mock"
        >
          <DashboardMock />
        </div>
      </div>
    </section>
  );
};

const DashboardMock = () => {
  const { lang } = useLang();
  const messages = lang === "ar" ? [
    { icon: MessageCircle, color: "text-emerald-600", bg: "bg-emerald-50", name: "محمد المعمري", channel: "واتساب", text: "السلام عليكم، أبي أعرف عن الطلب رقم #4521", time: "الآن", unread: true },
    { icon: Instagram, color: "text-pink-600", bg: "bg-pink-50", name: "فاطمة الزدجالي", channel: "انستقرام", text: "هل المنتج متوفر بلون آخر؟", time: "٢ د", unread: true },
    { icon: Facebook, color: "text-blue-600", bg: "bg-blue-50", name: "خالد البلوشي", channel: "فيسبوك", text: "شكراً جزيلاً على الخدمة الممتازة!", time: "٥ د", unread: false },
    { icon: Mail, color: "text-amber-600", bg: "bg-amber-50", name: "Sarah Al-Said", channel: "البريد", text: "Inquiry about bulk pricing for...", time: "١٢ د", unread: false },
  ] : [
    { icon: MessageCircle, color: "text-emerald-600", bg: "bg-emerald-50", name: "Mohammed Al-Maamari", channel: "WhatsApp", text: "Hi, I'd like to check order #4521", time: "now", unread: true },
    { icon: Instagram, color: "text-pink-600", bg: "bg-pink-50", name: "Fatma Al-Zadjali", channel: "Instagram", text: "Is this product available in another color?", time: "2m", unread: true },
    { icon: Facebook, color: "text-blue-600", bg: "bg-blue-50", name: "Khalid Al-Balushi", channel: "Facebook", text: "Thanks a lot for the great service!", time: "5m", unread: false },
    { icon: Mail, color: "text-amber-600", bg: "bg-amber-50", name: "Sarah Al-Said", channel: "Email", text: "Inquiry about bulk pricing for...", time: "12m", unread: false },
  ];

  return (
    <div className="relative max-w-5xl mx-auto">
      {/* Glow */}
      <div className="absolute -inset-4 bg-gradient-to-tr from-emerald-200/40 via-amber-100/30 to-emerald-200/40 rounded-3xl blur-2xl"></div>

      <div className="relative bg-white border border-stone-200 rounded-3xl shadow-2xl shadow-emerald-900/10 overflow-hidden">
        {/* Top bar */}
        <div className="flex items-center gap-2 px-4 py-3 bg-stone-50 border-b border-stone-200">
          <div className="flex gap-1.5">
            <div className="w-3 h-3 rounded-full bg-red-400"></div>
            <div className="w-3 h-3 rounded-full bg-amber-400"></div>
            <div className="w-3 h-3 rounded-full bg-emerald-400"></div>
          </div>
          <div className="flex-1 text-center text-xs text-stone-400 font-mono">app.socialhub.om</div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] min-h-[420px]">
          {/* Inbox List */}
          <div className="border-e border-stone-200 bg-stone-50/50">
            <div className="px-4 py-3 border-b border-stone-200">
              <h4 className="font-heading font-bold text-sm text-stone-800">
                {lang === "ar" ? "الرسائل الواردة" : "Inbox"}
              </h4>
              <p className="text-xs text-stone-500 mt-0.5">
                {lang === "ar" ? "٢٤ غير مقروءة" : "24 unread"}
              </p>
            </div>
            {messages.map((m, i) => (
              <div key={i} className={`flex gap-3 px-4 py-3 border-b border-stone-100 hover:bg-white transition-colors cursor-pointer ${i === 0 ? "bg-white border-s-2 border-s-emerald-700" : ""}`}>
                <div className={`flex-shrink-0 w-9 h-9 rounded-full ${m.bg} flex items-center justify-center`}>
                  <m.icon size={16} className={m.color} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-xs font-semibold text-stone-800 truncate">{m.name}</p>
                    <span className="text-[10px] text-stone-400 whitespace-nowrap">{m.time}</span>
                  </div>
                  <p className="text-xs text-stone-500 truncate mt-0.5">{m.text}</p>
                  <div className="flex items-center gap-1 mt-1">
                    <span className="text-[10px] text-stone-400">{m.channel}</span>
                    {m.unread && <span className="w-1.5 h-1.5 rounded-full bg-emerald-600"></span>}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {/* Conversation */}
          <div className="flex flex-col bg-white">
            <div className="px-5 py-3 border-b border-stone-200 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-full bg-emerald-100 flex items-center justify-center font-heading font-bold text-emerald-800 text-sm">
                  {lang === "ar" ? "م" : "M"}
                </div>
                <div>
                  <p className="text-sm font-semibold text-stone-800">{messages[0].name}</p>
                  <div className="flex items-center gap-1.5">
                    <MessageCircle size={11} className="text-emerald-600" />
                    <span className="text-[11px] text-stone-500">{messages[0].channel}</span>
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-1.5 px-2.5 py-1 bg-emerald-50 rounded-full">
                <Bot size={12} className="text-emerald-700" />
                <span className="text-[10px] font-semibold text-emerald-800">
                  {lang === "ar" ? "الذكاء الاصطناعي مفعّل" : "AI active"}
                </span>
              </div>
            </div>

            <div className="flex-1 p-5 space-y-3 bg-stone-50/30">
              <div className="flex">
                <div className="bg-white border border-stone-200 rounded-2xl rounded-ss-sm px-4 py-2.5 max-w-[75%] shadow-sm">
                  <p className="text-sm text-stone-700">{messages[0].text}</p>
                  <p className="text-[10px] text-stone-400 mt-1">10:24</p>
                </div>
              </div>
              <div className="flex justify-end">
                <div className="bg-emerald-700 text-white rounded-2xl rounded-se-sm px-4 py-2.5 max-w-[75%] shadow-sm">
                  <p className="text-sm">
                    {lang === "ar"
                      ? "وعليكم السلام محمد. طلبك #4521 جاهز للتسليم غداً بين ٩ صباحاً و١٢ ظهراً ✨"
                      : "Hi Mohammed! Your order #4521 is ready for delivery tomorrow between 9 AM and 12 PM ✨"}
                  </p>
                  <div className="flex items-center justify-end gap-1 mt-1">
                    <span className="text-[10px] text-emerald-100">10:24</span>
                    <CheckCheck size={12} className="text-emerald-200" />
                  </div>
                </div>
              </div>
              <div className="flex">
                <div className="bg-white border border-stone-200 rounded-2xl rounded-ss-sm px-4 py-2.5 shadow-sm">
                  <div className="flex gap-1">
                    <span className="w-1.5 h-1.5 bg-stone-400 rounded-full animate-pulse"></span>
                    <span className="w-1.5 h-1.5 bg-stone-400 rounded-full animate-pulse" style={{ animationDelay: "0.2s" }}></span>
                    <span className="w-1.5 h-1.5 bg-stone-400 rounded-full animate-pulse" style={{ animationDelay: "0.4s" }}></span>
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-stone-200 p-3 flex items-center gap-2">
              <input
                type="text"
                placeholder={lang === "ar" ? "اكتب ردك..." : "Type your reply..."}
                className="flex-1 bg-stone-100 rounded-xl px-3 py-2 text-sm text-stone-700 placeholder:text-stone-400 outline-none"
                disabled
              />
              <button className="bg-emerald-800 text-white rounded-xl p-2">
                <Arrow lang={lang} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Floating cards */}
      <div className="hidden md:block absolute -top-6 -start-8 animate-float">
        <FloatingCard icon={Bot} title={lang === "ar" ? "وُفّر ٤ ساعات/يوم" : "Saved 4 hrs/day"} sub={lang === "ar" ? "ذكاء اصطناعي" : "AI automation"} color="emerald" />
      </div>
      <div className="hidden md:block absolute -bottom-6 -end-8 animate-float-delayed">
        <FloatingCard icon={CheckCheck} title={lang === "ar" ? "+٤٢٪ تحويلات" : "+42% conversions"} sub={lang === "ar" ? "هذا الشهر" : "this month"} color="amber" />
      </div>
    </div>
  );
};

const Arrow = ({ lang }) => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ transform: lang === "ar" ? "scaleX(-1)" : "none" }}>
    <line x1="22" y1="2" x2="11" y2="13"></line>
    <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
  </svg>
);

const FloatingCard = ({ icon: Icon, title, sub, color }) => {
  const colors = {
    emerald: "bg-emerald-700 text-white",
    amber: "bg-amber-600 text-white",
  };
  return (
    <div className="bg-white rounded-2xl shadow-2xl p-3 flex items-center gap-3 border border-stone-100">
      <div className={`w-10 h-10 rounded-xl ${colors[color]} flex items-center justify-center`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-sm font-heading font-bold text-stone-800">{title}</p>
        <p className="text-[11px] text-stone-500">{sub}</p>
      </div>
    </div>
  );
};
