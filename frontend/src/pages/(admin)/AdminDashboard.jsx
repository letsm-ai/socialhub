import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  TrendingUp,
  Users,
  Wallet,
  MessageSquare,
  Loader2,
  ArrowUpRight,
  Activity,
  ShieldCheck,
  CheckCircle2,
  XCircle,
} from "lucide-react";

export default function AdminDashboard() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [downgrading, setDowngrading] = useState(false);
  const [downgradeResult, setDowngradeResult] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/admin/overview");
        setData(data);
      } catch (e) {
        setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
      }
    })();
  }, []);

  if (error) return <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-800">{error}</div>;
  if (!data) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="admin-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  const fmt = (n) => n.toLocaleString(lang === "ar" ? "ar-EG" : "en-US");

  const runDowngrade = async () => {
    if (!window.confirm(
      lang === "ar"
        ? "سيتم تحويل كل العملاء الحاليين إلى دور 'موظف' داخل Chatwoot لمنعهم من إنشاء قنوات مباشرة. هل تريد المتابعة؟"
        : "All existing clients will be demoted to 'agent' role inside Chatwoot, preventing them from creating channels directly. Continue?"
    )) return;
    setDowngrading(true);
    setDowngradeResult(null);
    try {
      const { data } = await api.post("/admin/chatwoot/downgrade-clients-to-agent");
      setDowngradeResult(data);
    } catch (e) {
      setDowngradeResult({
        error: formatApiErrorDetail(e.response?.data?.detail) || e.message,
      });
    } finally {
      setDowngrading(false);
    }
  };

  return (
    <div className="space-y-6" data-testid="admin-overview">
      <div>
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "نظرة عامة على المنصة" : "Platform Overview"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar" ? "إحصائيات الأعمال اللحظية لسوشال هَب." : "Real-time business metrics for SocialHub."}
        </p>
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <KpiCard
          testId="kpi-mrr"
          label={lang === "ar" ? "الإيراد الشهري (MRR)" : "Monthly Recurring Revenue"}
          value={`${data.mrr_omr.toFixed(2)}`}
          suffix={lang === "ar" ? "ر.ع" : "OMR"}
          icon={TrendingUp}
          accent="emerald"
        />
        <KpiCard
          testId="kpi-active-subs"
          label={lang === "ar" ? "المشتركون النشطون" : "Active Subscribers"}
          value={fmt(data.active_subscribers)}
          sub={`${fmt(data.trialing_subscribers)} ${lang === "ar" ? "في فترة تجربة" : "trialing"}`}
          icon={Users}
          accent="amber"
        />
        <KpiCard
          testId="kpi-messages"
          label={lang === "ar" ? "إجمالي الرسائل المُرسلة" : "Total Promotional Sent"}
          value={fmt(data.total_promotional_messages_sent)}
          sub={lang === "ar" ? "عبر جميع العملاء" : "across all clients"}
          icon={MessageSquare}
          accent="emerald"
        />
        <KpiCard
          testId="kpi-wallets"
          label={lang === "ar" ? "إجمالي أرصدة المحافظ" : "Total Wallet Balances"}
          value={`${data.total_wallet_balance_omr.toFixed(2)}`}
          suffix={lang === "ar" ? "ر.ع" : "OMR"}
          icon={Wallet}
          accent="amber"
        />
      </div>

      {/* Tier breakdown */}
      <Card data-testid="tier-breakdown-card" className="rounded-3xl border-stone-200">
        <CardHeader>
          <CardTitle className="text-base font-heading font-bold text-stone-900 flex items-center gap-2">
            <Activity size={18} className="text-emerald-700" />
            {lang === "ar" ? "توزيع المشتركين على الباقات" : "Subscriber distribution by plan"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            {[
              { key: "GROWTH", name_ar: "النمو", name_en: "Growth", price: 35, color: "bg-emerald-100 text-emerald-800" },
              { key: "PRO", name_ar: "المحترف", name_en: "Pro", price: 75, color: "bg-emerald-700 text-white" },
              { key: "ENTERPRISE", name_ar: "المؤسسات", name_en: "Enterprise", price: 150, color: "bg-stone-900 text-amber-300" },
            ].map((t) => {
              const count = data.tier_breakdown[t.key] || 0;
              const revenue = count * t.price;
              return (
                <div
                  key={t.key}
                  data-testid={`tier-${t.key.toLowerCase()}`}
                  className={`rounded-2xl p-5 ${t.color}`}
                >
                  <div className="text-xs font-bold uppercase tracking-wider opacity-80 mb-1">
                    {lang === "ar" ? t.name_ar : t.name_en}
                  </div>
                  <div className="font-heading text-3xl font-bold">{fmt(count)}</div>
                  <div className="text-xs mt-1 opacity-80">
                    {revenue.toFixed(0)} {lang === "ar" ? "ر.ع شهرياً" : "OMR/mo"}
                  </div>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Maintenance — Chatwoot lockdown */}
      <Card data-testid="chatwoot-lockdown-card" className="rounded-3xl border-stone-200">
        <CardHeader>
          <CardTitle className="text-base font-heading font-bold text-stone-900 flex items-center gap-2">
            <ShieldCheck size={18} className="text-emerald-700" />
            {lang === "ar" ? "قفل Chatwoot للعملاء" : "Chatwoot client lockdown"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-stone-600 leading-relaxed">
            {lang === "ar"
              ? "حوّل كل العملاء الحاليين من دور (Administrator) إلى دور (Agent) داخل Chatwoot — حتى لا يتمكنوا من إنشاء قنوات مباشرة من هناك. يُنفّذ مرة واحدة وآمن للتشغيل المتكرر."
              : "Demote every existing client from administrator → agent inside Chatwoot, so they can never create channels there. Idempotent: safe to run multiple times."}
          </p>
          <Button
            data-testid="chatwoot-downgrade-btn"
            onClick={runDowngrade}
            disabled={downgrading}
            className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl"
          >
            {downgrading ? (
              <Loader2 className="animate-spin me-2" size={16} />
            ) : (
              <ShieldCheck className="me-2" size={16} />
            )}
            {lang === "ar" ? "تشغيل الترقية العكسية الآن" : "Run downgrade now"}
          </Button>

          {downgradeResult && (
            <div
              data-testid="downgrade-result"
              className="rounded-xl border border-stone-200 bg-stone-50/60 p-4 space-y-2"
            >
              {downgradeResult.error ? (
                <div className="text-sm text-red-700 flex items-center gap-2">
                  <XCircle size={16} /> {downgradeResult.error}
                </div>
              ) : (
                <>
                  <div className="text-sm font-semibold text-stone-800">
                    {lang === "ar"
                      ? `إجمالي العملاء المعالَجين: ${downgradeResult.total}`
                      : `Total clients processed: ${downgradeResult.total}`}
                  </div>
                  <ul className="text-xs space-y-1 max-h-60 overflow-auto">
                    {(downgradeResult.results || []).map((r, i) => (
                      <li key={i} className="flex items-center gap-2">
                        {r.ok ? (
                          <CheckCircle2 size={12} className="text-emerald-600 shrink-0" />
                        ) : (
                          <XCircle size={12} className="text-red-600 shrink-0" />
                        )}
                        <span className="text-stone-700 font-mono">{r.email}</span>
                        {r.error && (
                          <span className="text-red-600 truncate">— {r.error}</span>
                        )}
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const KpiCard = ({ label, value, suffix, sub, icon: Icon, accent, testId }) => {
  const accents = {
    emerald: { bg: "bg-emerald-50", text: "text-emerald-800", border: "border-emerald-100" },
    amber: { bg: "bg-amber-50", text: "text-amber-800", border: "border-amber-100" },
  }[accent];
  return (
    <Card data-testid={testId} className="rounded-3xl border-stone-200 hover:-translate-y-1 transition-all hover:shadow-lg">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-3">
          <div className={`w-11 h-11 rounded-2xl ${accents.bg} ${accents.border} border flex items-center justify-center`}>
            <Icon size={20} className={accents.text} />
          </div>
          <ArrowUpRight size={16} className="text-stone-300" />
        </div>
        <div className="text-xs font-semibold text-stone-500 mb-1">{label}</div>
        <div className="flex items-baseline gap-1">
          <span className="font-heading text-3xl font-bold text-stone-900">{value}</span>
          {suffix && <span className="text-sm font-semibold text-stone-500">{suffix}</span>}
        </div>
        {sub && <div className="text-xs text-stone-400 mt-1.5">{sub}</div>}
      </CardContent>
    </Card>
  );
};
