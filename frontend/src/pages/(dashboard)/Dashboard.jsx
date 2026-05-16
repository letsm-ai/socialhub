import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useLang } from "@/contexts/LanguageContext";
import { useAuth, api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  Sparkles,
  CreditCard,
  Wallet,
  TrendingUp,
  CheckCircle2,
  AlertCircle,
  Clock,
  Loader2,
} from "lucide-react";
import { Link } from "react-router-dom";

const TIER_LABELS = {
  GROWTH: { ar: "النمو", en: "Growth", color: "emerald" },
  PRO: { ar: "المحترف", en: "Pro", color: "emerald" },
  ENTERPRISE: { ar: "المؤسسات", en: "Enterprise", color: "amber" },
};

const STATUS_LABELS = {
  TRIALING: { ar: "تجربة مجانية", en: "Trial", color: "amber", icon: Sparkles },
  ACTIVE: { ar: "نشط", en: "Active", color: "emerald", icon: CheckCircle2 },
  PAST_DUE: { ar: "متأخر", en: "Past due", color: "red", icon: AlertCircle },
  CANCELED: { ar: "ملغى", en: "Canceled", color: "stone", icon: AlertCircle },
};

export default function Dashboard() {
  const { lang } = useLang();
  const { user } = useAuth();
  const [account, setAccount] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/me/account");
        setAccount(data);
      } catch (e) {
        setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
      }
    })();
  }, []);

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-800" data-testid="dashboard-error">
        {error}
      </div>
    );
  }

  if (!account) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="dashboard-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  const tier = TIER_LABELS[account.subscription?.plan_tier] || TIER_LABELS.GROWTH;
  const status = STATUS_LABELS[account.subscription?.status] || STATUS_LABELS.TRIALING;
  const StatusIcon = status.icon;
  const periodEnd = account.subscription?.current_period_end
    ? new Date(account.subscription.current_period_end).toLocaleDateString(lang === "ar" ? "ar-OM" : "en-OM", {
        year: "numeric", month: "long", day: "numeric",
      })
    : "—";
  const companyName = account.user?.company_name || user?.company_name || "";

  return (
    <div className="space-y-6" data-testid="dashboard-overview">
      {/* Greeting */}
      <div>
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? `أهلاً، ${user?.name?.split(" ")[0] || ""} 👋` : `Hi ${user?.name?.split(" ")[0] || ""} 👋`}
        </h1>
        {companyName && (
          <div data-testid="dashboard-company-name" className="mt-2 inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-50 border border-emerald-200">
            <div className="w-1.5 h-1.5 rounded-full bg-emerald-600"></div>
            <span className="text-xs font-semibold text-emerald-900">{companyName}</span>
          </div>
        )}
        <p className="text-stone-600 mt-2 text-sm">
          {lang === "ar"
            ? "هذه نظرة سريعة على حسابك في سوشال هَب."
            : "Here's a quick view of your SocialHub account."}
        </p>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        <Card data-testid="plan-card" className="rounded-2xl border-stone-200">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold text-stone-600 flex items-center gap-2">
                <CreditCard size={16} className="text-emerald-700" />
                {lang === "ar" ? "الباقة الحالية" : "Current plan"}
              </CardTitle>
              <Badge variant="outline" className={`text-[10px] font-bold uppercase tracking-wider border-${tier.color}-200 text-${tier.color}-800 bg-${tier.color}-50`}>
                {tier[lang]}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <div className="font-heading text-3xl font-bold text-stone-900 mb-3">{tier[lang]}</div>
            <Link to="/dashboard/billing">
              <Button variant="outline" size="sm" data-testid="manage-plan-btn" className="rounded-xl border-stone-300 hover:border-emerald-700 hover:text-emerald-800">
                {lang === "ar" ? "إدارة الباقة" : "Manage plan"}
              </Button>
            </Link>
          </CardContent>
        </Card>

        <Card data-testid="status-card" className="rounded-2xl border-stone-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-stone-600 flex items-center gap-2">
              <Clock size={16} className="text-emerald-700" />
              {lang === "ar" ? "حالة الاشتراك" : "Subscription status"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 mb-3">
              <div className={`w-9 h-9 rounded-xl bg-${status.color}-50 border border-${status.color}-100 flex items-center justify-center`}>
                <StatusIcon size={18} className={`text-${status.color}-700`} />
              </div>
              <div>
                <div className="font-heading text-xl font-bold text-stone-900">{status[lang]}</div>
              </div>
            </div>
            <p className="text-xs text-stone-500">
              {lang === "ar" ? "تنتهي الفترة في" : "Period ends on"}: <span className="font-semibold text-stone-700">{periodEnd}</span>
            </p>
          </CardContent>
        </Card>

        <Card data-testid="credits-card" className="rounded-2xl border-stone-200">
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold text-stone-600 flex items-center gap-2">
              <Wallet size={16} className="text-emerald-700" />
              {lang === "ar" ? "رصيد الرسائل الترويجية" : "Promotional credits"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-1 mb-3">
              <span className="font-heading text-3xl font-bold text-stone-900">{account.wallet?.promotional_credits ?? 0}</span>
              <span className="text-sm text-stone-500">{lang === "ar" ? "رسالة" : "msgs"}</span>
            </div>
            <Button size="sm" data-testid="buy-credits-btn" className="rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white h-8 px-4 text-xs">
              <Sparkles size={12} className="me-1.5" />
              {lang === "ar" ? "شراء رصيد" : "Buy credits"}
            </Button>
          </CardContent>
        </Card>
      </div>

      {/* Usage card */}
      <Card data-testid="usage-card" className="rounded-2xl border-stone-200">
        <CardHeader>
          <CardTitle className="text-base font-heading font-bold text-stone-900 flex items-center gap-2">
            <TrendingUp size={18} className="text-emerald-700" />
            {lang === "ar" ? "نشاط هذا الشهر" : "This month's activity"}
          </CardTitle>
          <CardDescription className="text-stone-500">
            {lang === "ar" ? "ملخص سريع لأداء صندوق رسائلك." : "A quick snapshot of your inbox performance."}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <Mini value={account.wallet?.total_promotional_messages_sent ?? 0} label={lang === "ar" ? "رسائل مرسلة" : "Sent"} />
            <Mini value="—" label={lang === "ar" ? "محادثات نشطة" : "Active chats"} />
            <Mini value="—" label={lang === "ar" ? "متوسط زمن الرد" : "Avg response"} />
            <Mini value="—" label={lang === "ar" ? "معدّل الرضا" : "CSAT"} />
          </div>
          <p className="text-xs text-stone-400 mt-5">
            {lang === "ar"
              ? "ستظهر هذه المقاييس بعد ربط قناة WhatsApp ووصول أول الرسائل."
              : "These metrics will appear once a WhatsApp channel is connected and messages start flowing."}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}

const Mini = ({ value, label }) => (
  <div>
    <div className="font-heading text-2xl font-bold text-stone-900">{value}</div>
    <div className="text-xs text-stone-500 mt-0.5">{label}</div>
  </div>
);
