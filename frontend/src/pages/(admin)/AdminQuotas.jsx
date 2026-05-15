import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  Loader2, MessageSquare, Wallet, Users, Gift, Check, X, ArrowUpRight, Zap,
} from "lucide-react";

export default function AdminQuotas() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [bulkDialog, setBulkDialog] = useState({ open: false, omr: "", credits: "", note: "" });
  const [bulkBusy, setBulkBusy] = useState(false);

  const load = async () => {
    try {
      const { data } = await api.get("/admin/quotas");
      setData(data);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    }
  };

  useEffect(() => { load(); }, []);

  const showToast = (m) => { setToast(m); setTimeout(() => setToast(""), 3500); };

  const submitBulkGrant = async () => {
    const omr = parseFloat(bulkDialog.omr) || 0;
    const credits = parseInt(bulkDialog.credits) || 0;
    if (omr === 0 && credits === 0) {
      setError(lang === "ar" ? "أدخل مبلغاً أو رسائل" : "Enter OMR or credits");
      return;
    }
    setBulkBusy(true);
    try {
      const { data } = await api.post("/admin/quotas/bulk-grant", {
        omr_per_client: omr,
        credits_per_client: credits,
        note: bulkDialog.note || "Bulk promo",
      });
      setBulkDialog({ open: false, omr: "", credits: "", note: "" });
      showToast(
        lang === "ar"
          ? `🎁 تم منح ${data.granted_to} عميل!`
          : `🎁 Granted to ${data.granted_to} clients!`
      );
      await load();
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setBulkBusy(false);
    }
  };

  if (!data) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="admin-quotas-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  const fmt = (n) => Number(n).toLocaleString(lang === "ar" ? "ar-EG" : "en-US");
  const dateFmt = (iso) =>
    iso ? new Date(iso).toLocaleDateString(lang === "ar" ? "ar-OM" : "en-OM", { year: "numeric", month: "short", day: "numeric" }) : "—";

  return (
    <div className="space-y-6" data-testid="admin-quotas-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
            {lang === "ar" ? "حصص الرسائل والمحافظ" : "Message Quotas"}
          </h1>
          <p className="text-stone-600 mt-1 text-sm">
            {lang === "ar" ? "إدارة رصيد الرسائل عبر جميع العملاء." : "Manage messaging credits across all clients."}
          </p>
        </div>
        <Button
          data-testid="bulk-grant-btn"
          onClick={() => setBulkDialog({ open: true, omr: "", credits: "", note: "" })}
          className="rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-900 font-semibold h-11 px-5"
        >
          <Gift size={16} className="me-2" />
          {lang === "ar" ? "منح جماعي" : "Bulk grant"}
        </Button>
      </div>

      {toast && (
        <div data-testid="quotas-toast" className="bg-emerald-50 border border-emerald-200 rounded-2xl p-3.5 text-sm text-emerald-900 flex items-center gap-2">
          <Check size={16} className="text-emerald-700" /> {toast}
        </div>
      )}
      {error && (
        <div data-testid="quotas-error" className="bg-red-50 border border-red-200 rounded-2xl p-3.5 text-sm text-red-800 flex items-center gap-2">
          <X size={16} className="text-red-600" /> {error}
        </div>
      )}

      {/* Summary KPIs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Kpi testId="kpi-sent" label={lang === "ar" ? "إجمالي الرسائل المُرسلة" : "Total messages sent"} value={fmt(data.summary.total_messages_sent)} icon={MessageSquare} accent="emerald" />
        <Kpi testId="kpi-credits" label={lang === "ar" ? "الأرصدة المتبقية" : "Total credits remaining"} value={fmt(data.summary.total_credits_remaining)} icon={Zap} accent="amber" />
        <Kpi testId="kpi-balance" label={lang === "ar" ? "إجمالي المحافظ" : "Total wallet balance"} value={data.summary.total_balance_omr.toFixed(2)} suffix={lang === "ar" ? "ر.ع" : "OMR"} icon={Wallet} accent="emerald" />
        <Kpi testId="kpi-avg" label={lang === "ar" ? "متوسط الرصيد/عميل" : "Avg credits per client"} value={fmt(data.summary.avg_credits_per_client)} sub={`${data.summary.client_count} ${lang === "ar" ? "عميل" : "clients"}`} icon={Users} accent="amber" />
      </div>

      {/* Per-client quotas table */}
      <Card className="rounded-2xl border-stone-200 overflow-hidden">
        <CardHeader>
          <CardTitle className="font-heading text-base font-bold text-stone-900">
            {lang === "ar" ? "حصص العملاء" : "Per-client quotas"}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table data-testid="quotas-table">
              <TableHeader>
                <TableRow className="bg-stone-50 hover:bg-stone-50">
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "العميل" : "Client"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "الباقة" : "Plan"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600 text-end">{lang === "ar" ? "الرصيد (ر.ع)" : "Balance"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600 text-end">{lang === "ar" ? "رسائل متبقية" : "Credits"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600 text-end">{lang === "ar" ? "رسائل مُرسلة" : "Sent"}</TableHead>
                  <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "آخر شحن" : "Last topup"}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.rows.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-10 text-stone-500 text-sm">
                      {lang === "ar" ? "لا يوجد عملاء بعد" : "No clients yet"}
                    </TableCell>
                  </TableRow>
                ) : (
                  data.rows.map((r) => (
                    <TableRow key={r.user_id} data-testid={`quota-row-${r.user_id}`} className={!r.is_active ? "opacity-60" : ""}>
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-700 to-emerald-900 flex items-center justify-center font-heading font-bold text-white text-sm">
                            {r.name?.[0]?.toUpperCase() || "?"}
                          </div>
                          <div>
                            <div className="font-semibold text-stone-900 text-sm">{r.name || "—"}</div>
                            <div className="text-xs text-stone-500">{r.email}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="text-[10px] bg-stone-50 text-stone-700 border-stone-200">{r.plan_tier}</Badge>
                      </TableCell>
                      <TableCell className="text-end font-bold text-stone-900">{r.balance_omr.toFixed(2)}</TableCell>
                      <TableCell className="text-end font-mono text-emerald-800">{fmt(r.promotional_credits)}</TableCell>
                      <TableCell className="text-end font-mono text-stone-600">{fmt(r.total_promotional_messages_sent)}</TableCell>
                      <TableCell className="text-xs text-stone-500">{dateFmt(r.last_topup_at)}</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
      </Card>

      {/* Bulk grant dialog */}
      <Dialog open={bulkDialog.open} onOpenChange={(o) => !o && setBulkDialog({ open: false, omr: "", credits: "", note: "" })}>
        <DialogContent className="rounded-3xl" data-testid="bulk-grant-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading flex items-center gap-2">
              <Gift size={18} className="text-amber-500" />
              {lang === "ar" ? "منح جماعي لجميع العملاء" : "Bulk grant to all active clients"}
            </DialogTitle>
            <DialogDescription>
              {lang === "ar"
                ? `سيُضاف الرصيد لـ ${data.summary.client_count} عميل نشط.`
                : `Credits will be added to ${data.summary.client_count} active clients.`}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium text-stone-700 mb-1.5 block">
                  {lang === "ar" ? "مبلغ ر.ع لكل عميل" : "OMR per client"}
                </label>
                <Input
                  data-testid="bulk-omr"
                  type="number"
                  step="0.01"
                  value={bulkDialog.omr}
                  onChange={(e) => setBulkDialog((d) => ({ ...d, omr: e.target.value }))}
                  placeholder="5.00"
                  className="h-11 rounded-xl text-center font-mono"
                />
              </div>
              <div>
                <label className="text-sm font-medium text-stone-700 mb-1.5 block">
                  {lang === "ar" ? "رصيد رسائل" : "Message credits"}
                </label>
                <Input
                  data-testid="bulk-credits"
                  type="number"
                  step="1"
                  value={bulkDialog.credits}
                  onChange={(e) => setBulkDialog((d) => ({ ...d, credits: e.target.value }))}
                  placeholder="200"
                  className="h-11 rounded-xl text-center font-mono"
                />
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-stone-700 mb-1.5 block">
                {lang === "ar" ? "ملاحظة (اختياري)" : "Note (optional)"}
              </label>
              <Input
                data-testid="bulk-note"
                value={bulkDialog.note}
                onChange={(e) => setBulkDialog((d) => ({ ...d, note: e.target.value }))}
                placeholder={lang === "ar" ? "حملة ترويجية..." : "Promo campaign..."}
                className="h-11 rounded-xl"
              />
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkDialog({ open: false, omr: "", credits: "", note: "" })} className="rounded-xl">
              {lang === "ar" ? "إلغاء" : "Cancel"}
            </Button>
            <Button
              data-testid="bulk-submit"
              onClick={submitBulkGrant}
              disabled={bulkBusy}
              className="rounded-xl bg-amber-500 hover:bg-amber-400 text-stone-900 font-bold"
            >
              {bulkBusy ? <Loader2 className="animate-spin me-2" size={14} /> : <Gift size={14} className="me-2" />}
              {lang === "ar" ? "تطبيق المنح" : "Apply grant"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
