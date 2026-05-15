import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  Loader2, TrendingUp, Wallet, Receipt, Users, ArrowUpRight, CreditCard,
} from "lucide-react";

const TYPE_STYLES = {
  TOPUP: "bg-emerald-50 text-emerald-800 border-emerald-100",
  ADMIN_ADJUSTMENT: "bg-amber-50 text-amber-800 border-amber-100",
  ADMIN_BULK_GRANT: "bg-purple-50 text-purple-800 border-purple-100",
};

export default function AdminBilling() {
  const { lang } = useLang();
  const [overview, setOverview] = useState(null);
  const [transactions, setTransactions] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const [o, t] = await Promise.all([
          api.get("/admin/billing/overview"),
          api.get("/admin/transactions?limit=100"),
        ]);
        setOverview(o.data);
        setTransactions(t.data.transactions || []);
      } catch (e) {
        setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
      }
    })();
  }, []);

  if (error) return <div className="bg-red-50 border border-red-200 rounded-2xl p-4 text-red-800">{error}</div>;
  if (!overview) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="admin-billing-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  const fmt = (n) => Number(n).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");
  const dateFmt = (iso) =>
    iso
      ? new Date(iso).toLocaleString(lang === "ar" ? "ar-OM" : "en-OM", {
          month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
        })
      : "—";

  return (
    <div className="space-y-6" data-testid="admin-billing-page">
      <div>
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "الفوترة والإيرادات" : "Billing & Revenue"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar" ? "إيراد المنصة وجميع المعاملات المالية." : "Platform revenue and all financial transactions."}
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi testId="kpi-mrr" label={lang === "ar" ? "الإيراد الشهري (MRR)" : "MRR"} value={overview.mrr_omr.toFixed(2)} suffix={lang === "ar" ? "ر.ع" : "OMR"} icon={TrendingUp} accent="emerald" />
        <Kpi testId="kpi-mtd" label={lang === "ar" ? "إيراد الشحن هذا الشهر" : "Top-ups MTD"} value={overview.mtd_topup_revenue_omr.toFixed(2)} suffix={lang === "ar" ? "ر.ع" : "OMR"} icon={Wallet} accent="amber" />
        <Kpi testId="kpi-ltv" label={lang === "ar" ? "إجمالي عمليات الشحن" : "Lifetime top-ups"} value={overview.ltv_topup_revenue_omr.toFixed(2)} sub={`${overview.total_topup_count} ${lang === "ar" ? "عملية" : "txns"}`} suffix={lang === "ar" ? "ر.ع" : "OMR"} icon={Receipt} accent="emerald" />
        <Kpi testId="kpi-arpu" label={lang === "ar" ? "متوسط الإيراد لكل عميل" : "ARPU"} value={overview.arpu_omr.toFixed(2)} suffix={lang === "ar" ? "ر.ع" : "OMR"} icon={Users} accent="amber" />
      </div>

      <Card className="rounded-2xl border-stone-200" data-testid="transactions-card">
        <CardHeader>
          <CardTitle className="font-heading text-base font-bold text-stone-900 flex items-center gap-2">
            <Receipt size={18} className="text-emerald-700" />
            {lang === "ar" ? "أحدث المعاملات" : "Recent transactions"}
            <Badge variant="outline" className="border-stone-200 text-stone-600 ms-2">
              {transactions.length}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow className="bg-stone-50 hover:bg-stone-50">
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "العميل" : "Client"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "النوع" : "Type"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "الباقة" : "Package"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600 text-end">{lang === "ar" ? "الرسائل" : "Messages"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600 text-end">{lang === "ar" ? "المبلغ" : "Amount"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "التاريخ" : "Date"}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {transactions.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10 text-stone-500 text-sm">
                      {lang === "ar" ? "لا توجد معاملات بعد" : "No transactions yet"}
                    </TableCell>
                  </TableRow>
                ) : (
                  transactions.map((t) => (
                    <TableRow key={t.id} data-testid={`txn-row-${t.id}`}>
                      <TableCell>
                        <div className="text-sm font-semibold text-stone-900">{t.user_name}</div>
                        <div className="text-xs text-stone-500">{t.user_email}</div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className={`text-[10px] ${TYPE_STYLES[t.type] || "bg-stone-50 text-stone-600 border-stone-200"}`}>
                          {t.type}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-sm text-stone-700">{t.package_name || "—"}</TableCell>
                      <TableCell className="text-end font-mono text-sm">{fmt(t.messages || 0)}</TableCell>
                      <TableCell className="text-end font-bold text-emerald-800">
                        {t.amount_omr >= 0 ? "+" : ""}{t.amount_omr.toFixed(2)} <span className="text-xs text-stone-500 ms-1">{lang === "ar" ? "ر.ع" : "OMR"}</span>
                      </TableCell>
                      <TableCell className="text-xs text-stone-500">{dateFmt(t.created_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Stripe events */}
      <Card className="rounded-2xl border-stone-200" data-testid="stripe-events-card">
        <CardHeader>
          <CardTitle className="font-heading text-base font-bold text-stone-900 flex items-center gap-2">
            <CreditCard size={18} className="text-emerald-700" />
            {lang === "ar" ? "أحداث Stripe الأخيرة" : "Recent Stripe events"}
            <Badge variant="outline" className="border-amber-200 text-amber-800 bg-amber-50 text-[10px] ms-2">MOCKED</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {overview.stripe_events_recent.length === 0 ? (
            <p className="text-sm text-stone-500 text-center py-6">
              {lang === "ar" ? "لا توجد أحداث Stripe بعد. سيُفعَّل عند ربط Stripe الحقيقي." : "No Stripe events yet. Will activate when Stripe is wired."}
            </p>
          ) : (
            <ul className="space-y-2">
              {overview.stripe_events_recent.map((e, i) => (
                <li key={i} className="flex items-center justify-between text-sm py-2 border-b border-stone-100 last:border-0">
                  <span className="font-mono text-xs text-stone-700">{e.size} bytes · signed: {String(e.signed)}</span>
                  <span className="text-xs text-stone-500">{dateFmt(e.received_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

const Kpi = ({ label, value, suffix, sub, icon: Icon, accent, testId }) => {
  const A = { emerald: { bg: "bg-emerald-50", text: "text-emerald-800", border: "border-emerald-100" },
              amber: { bg: "bg-amber-50", text: "text-amber-800", border: "border-amber-100" } }[accent];
  return (
    <Card data-testid={testId} className="rounded-3xl border-stone-200 hover:-translate-y-1 transition-all hover:shadow-lg">
      <CardContent className="p-6">
        <div className="flex items-start justify-between mb-3">
          <div className={`w-11 h-11 rounded-2xl ${A.bg} ${A.border} border flex items-center justify-center`}>
            <Icon size={20} className={A.text} />
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
