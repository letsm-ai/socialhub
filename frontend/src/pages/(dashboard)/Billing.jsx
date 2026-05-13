import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import { Check, Sparkles, Loader2, CreditCard, ArrowRight, ArrowLeft, ShieldCheck } from "lucide-react";

const TIER_ORDER = { GROWTH: 1, PRO: 2, ENTERPRISE: 3 };

export default function Billing() {
  const { lang } = useLang();
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;
  const [account, setAccount] = useState(null);
  const [plans, setPlans] = useState([]);
  const [error, setError] = useState("");
  const [upgradingTo, setUpgradingTo] = useState(null);
  const [toast, setToast] = useState("");

  const load = async () => {
    try {
      const [a, p] = await Promise.all([api.get("/me/account"), api.get("/plans")]);
      setAccount(a.data);
      setPlans(p.data.plans);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onUpgrade = async (tier) => {
    setUpgradingTo(tier);
    setError("");
    try {
      const { data } = await api.post("/me/subscription/upgrade", { target_tier: tier });
      setAccount((a) => ({ ...a, subscription: data.subscription }));
      setToast(
        lang === "ar"
          ? `تم تحديث اشتراكك إلى باقة ${tier === "PRO" ? "المحترف" : tier === "GROWTH" ? "النمو" : "المؤسسات"} ✨`
          : `Plan updated to ${tier} ✨`
      );
      setTimeout(() => setToast(""), 4000);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setUpgradingTo(null);
    }
  };

  if (!account || plans.length === 0) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="billing-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  const currentTier = account.subscription?.plan_tier || "GROWTH";
  const currentPlan = plans.find((p) => p.tier === currentTier);
  const periodEnd = account.subscription?.current_period_end
    ? new Date(account.subscription.current_period_end).toLocaleDateString(lang === "ar" ? "ar-OM" : "en-OM", {
        year: "numeric", month: "long", day: "numeric",
      })
    : "—";

  return (
    <div className="space-y-6" data-testid="billing-page">
      <div>
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "الفوترة والاشتراك" : "Billing & subscription"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar" ? "أدر باقتك، رصيدك، وفواتيرك." : "Manage your plan, credits, and invoices."}
        </p>
      </div>

      {toast && (
        <div data-testid="billing-toast" className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-sm text-emerald-900 flex items-center gap-2">
          <Check size={16} className="text-emerald-700" />
          {toast}
        </div>
      )}
      {error && (
        <div data-testid="billing-error" className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Current plan card */}
      <Card data-testid="current-plan-card" className="rounded-3xl border-stone-200 overflow-hidden">
        <CardContent className="p-0">
          <div className="grid grid-cols-1 md:grid-cols-[1fr_280px]">
            <div className="p-8 md:p-10">
              <div className="flex items-center gap-2 mb-3">
                <Badge className="bg-emerald-50 text-emerald-800 border border-emerald-100 hover:bg-emerald-50">
                  {lang === "ar" ? "الباقة الحالية" : "Current plan"}
                </Badge>
                <Badge
                  variant="outline"
                  className={`border-${account.subscription?.status === "ACTIVE" ? "emerald" : "amber"}-200 text-${account.subscription?.status === "ACTIVE" ? "emerald" : "amber"}-800 bg-${account.subscription?.status === "ACTIVE" ? "emerald" : "amber"}-50`}
                >
                  {account.subscription?.status === "TRIALING"
                    ? lang === "ar" ? "تجربة مجانية" : "Trial"
                    : lang === "ar" ? "نشط" : "Active"}
                </Badge>
              </div>
              <h2 className="font-heading text-3xl md:text-4xl font-bold text-stone-900 mb-2">
                {lang === "ar" ? currentPlan?.name_ar : currentPlan?.name_en}
              </h2>
              <div className="flex items-baseline gap-1 mb-4">
                <span className="font-heading text-4xl font-bold text-stone-900">{currentPlan?.price_omr}</span>
                <span className="text-stone-500 text-sm">
                  {lang === "ar" ? "ر.ع / شهرياً" : "OMR / month"}
                </span>
              </div>
              <p className="text-sm text-stone-500 flex items-center gap-1.5">
                <Sparkles size={14} className="text-emerald-700" />
                {lang === "ar" ? "تنتهي فترة التجربة في" : "Period ends on"}: <span className="font-semibold text-stone-700">{periodEnd}</span>
              </p>

              <ul className="mt-6 space-y-2.5">
                {(lang === "ar" ? currentPlan?.features_ar : currentPlan?.features_en)?.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-stone-700">
                    <div className="flex-shrink-0 w-5 h-5 rounded-full bg-emerald-50 flex items-center justify-center mt-0.5">
                      <Check size={12} className="text-emerald-700" strokeWidth={3} />
                    </div>
                    {f}
                  </li>
                ))}
              </ul>
            </div>

            <div className="bg-stone-50 border-s border-stone-200 p-8 md:p-10 flex flex-col justify-center">
              <div className="text-xs font-bold uppercase tracking-wider text-stone-500 mb-3">
                {lang === "ar" ? "إجراءات سريعة" : "Quick actions"}
              </div>
              <Button
                data-testid="upgrade-plan-btn"
                onClick={() => {
                  const target = currentTier === "GROWTH" ? "PRO" : "ENTERPRISE";
                  document.getElementById(`plan-${target}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
                }}
                className="w-full bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl h-12 mb-3"
                disabled={currentTier === "ENTERPRISE"}
              >
                <Sparkles size={16} className="me-2" />
                {currentTier === "ENTERPRISE"
                  ? lang === "ar" ? "أنت على أعلى باقة" : "On highest plan"
                  : lang === "ar" ? "ترقية الباقة" : "Upgrade plan"}
                {currentTier !== "ENTERPRISE" && <Arrow className="ms-2" size={16} />}
              </Button>
              <Button variant="outline" data-testid="invoices-btn" className="w-full rounded-xl h-11 border-stone-300">
                <CreditCard size={16} className="me-2" />
                {lang === "ar" ? "الفواتير" : "Invoices"}
              </Button>
              <p className="text-[11px] text-stone-400 mt-4 leading-relaxed">
                {lang === "ar"
                  ? "الترقية فورية. سيتم احتساب الفرق بالتناسب."
                  : "Upgrades are instant. Pro-rata adjustment applies."}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Available plans */}
      <div>
        <h2 className="font-heading text-xl md:text-2xl font-bold text-stone-900 mb-1">
          {lang === "ar" ? "كل الباقات" : "All plans"}
        </h2>
        <p className="text-stone-500 text-sm mb-6">
          {lang === "ar" ? "اختر الباقة المناسبة لحجم فريقك." : "Pick the plan that fits your team size."}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {plans.map((p) => {
            const isCurrent = p.tier === currentTier;
            const isDowngrade = TIER_ORDER[p.tier] < TIER_ORDER[currentTier];
            const highlight = p.tier === "PRO";
            return (
              <Card
                key={p.tier}
                id={`plan-${p.tier}`}
                data-testid={`plan-card-${p.tier.toLowerCase()}`}
                className={`rounded-3xl transition-all ${
                  isCurrent
                    ? "border-2 border-emerald-700 shadow-lg"
                    : highlight
                    ? "border-stone-200 hover:border-emerald-300 hover:-translate-y-1"
                    : "border-stone-200 hover:-translate-y-1"
                }`}
              >
                <CardHeader>
                  <div className="flex items-center justify-between mb-1">
                    <CardTitle className="font-heading text-lg font-bold text-stone-900">
                      {lang === "ar" ? p.name_ar : p.name_en}
                    </CardTitle>
                    {isCurrent && (
                      <Badge className="bg-emerald-700 text-white hover:bg-emerald-700">
                        <ShieldCheck size={12} className="me-1" />
                        {lang === "ar" ? "حالياً" : "Current"}
                      </Badge>
                    )}
                  </div>
                  <div className="flex items-baseline gap-1">
                    <span className="font-heading text-3xl font-bold text-stone-900">{p.price_omr}</span>
                    <span className="text-xs text-stone-500">
                      {lang === "ar" ? "ر.ع / شهرياً" : "OMR / mo"}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <ul className="space-y-2 mb-5">
                    {(lang === "ar" ? p.features_ar : p.features_en).map((f, i) => (
                      <li key={i} className="flex items-start gap-2 text-xs text-stone-600">
                        <Check size={12} className="text-emerald-700 mt-0.5 flex-shrink-0" strokeWidth={3} />
                        {f}
                      </li>
                    ))}
                  </ul>
                  <Button
                    data-testid={`upgrade-to-${p.tier.toLowerCase()}-btn`}
                    onClick={() => !isCurrent && onUpgrade(p.tier)}
                    disabled={isCurrent || upgradingTo === p.tier}
                    className={`w-full rounded-xl h-11 ${
                      isCurrent
                        ? "bg-stone-100 text-stone-500 hover:bg-stone-100 cursor-default"
                        : "bg-emerald-800 hover:bg-emerald-900 text-white"
                    }`}
                  >
                    {upgradingTo === p.tier ? (
                      <Loader2 className="animate-spin" size={16} />
                    ) : isCurrent ? (
                      lang === "ar" ? "باقتك الحالية" : "Your plan"
                    ) : isDowngrade ? (
                      lang === "ar" ? "تخفيض الباقة" : "Downgrade"
                    ) : (
                      lang === "ar" ? "الترقية" : "Upgrade"
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}
