import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter,
} from "@/components/ui/dialog";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  Search, ArrowUpDown, Loader2, Check, X, Pause, Play, Plus, Minus, Wallet, Users,
} from "lucide-react";

const STATUS_STYLES = {
  ACTIVE: "bg-emerald-50 text-emerald-800 border-emerald-100",
  TRIALING: "bg-amber-50 text-amber-800 border-amber-100",
  PAST_DUE: "bg-red-50 text-red-800 border-red-100",
  CANCELED: "bg-stone-100 text-stone-600 border-stone-200",
  "—": "bg-stone-50 text-stone-500 border-stone-200",
};

const PLAN_STYLES = {
  GROWTH: "bg-emerald-50 text-emerald-800 border-emerald-100",
  PRO: "bg-emerald-700 text-white border-emerald-700",
  ENTERPRISE: "bg-stone-900 text-amber-300 border-stone-900",
  "—": "bg-stone-50 text-stone-500 border-stone-200",
};

export default function AdminClients() {
  const { lang } = useLang();
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");

  // Filtering + sorting
  const [search, setSearch] = useState("");
  const [planFilter, setPlanFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("created_at");
  const [sortDir, setSortDir] = useState("desc");

  // Dialogs
  const [creditDialog, setCreditDialog] = useState({ open: false, client: null, amount: "", note: "" });
  const [busy, setBusy] = useState(null); // { id, action }

  const load = async () => {
    try {
      const { data } = await api.get("/admin/clients");
      setClients(data.clients || []);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const showToast = (msg) => { setToast(msg); setTimeout(() => setToast(""), 3500); };

  const filtered = useMemo(() => {
    let rows = [...clients];
    if (search.trim()) {
      const q = search.toLowerCase();
      rows = rows.filter((c) =>
        (c.name || "").toLowerCase().includes(q) ||
        (c.email || "").toLowerCase().includes(q) ||
        (c.company_name || "").toLowerCase().includes(q) ||
        (c.whatsapp_phone || "").toLowerCase().includes(q)
      );
    }
    if (planFilter !== "all") rows = rows.filter((c) => c.plan_tier === planFilter);
    if (statusFilter !== "all") rows = rows.filter((c) => c.status === statusFilter);

    rows.sort((a, b) => {
      const av = a[sortBy];
      const bv = b[sortBy];
      if (av == null && bv == null) return 0;
      if (av == null) return 1;
      if (bv == null) return -1;
      if (typeof av === "number" && typeof bv === "number") return sortDir === "asc" ? av - bv : bv - av;
      return sortDir === "asc"
        ? String(av).localeCompare(String(bv))
        : String(bv).localeCompare(String(av));
    });
    return rows;
  }, [clients, search, planFilter, statusFilter, sortBy, sortDir]);

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortBy(col); setSortDir("asc"); }
  };

  const toggleStatus = async (client) => {
    setBusy({ id: client.id, action: "status" });
    try {
      await api.post(`/admin/clients/${client.id}/status`, { is_active: !client.is_active });
      showToast(
        !client.is_active
          ? (lang === "ar" ? "تم تفعيل الحساب" : "Client activated")
          : (lang === "ar" ? "تم تعليق الحساب" : "Client suspended")
      );
      await load();
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(null);
    }
  };

  const submitCredit = async () => {
    const amount = parseFloat(creditDialog.amount);
    if (Number.isNaN(amount) || amount === 0) {
      setError(lang === "ar" ? "أدخل مبلغاً صحيحاً غير صفر" : "Enter a valid non-zero amount");
      return;
    }
    setBusy({ id: creditDialog.client.id, action: "credit" });
    try {
      await api.post(`/admin/clients/${creditDialog.client.id}/wallet/credit`, {
        amount_omr: amount,
        note: creditDialog.note || null,
      });
      setCreditDialog({ open: false, client: null, amount: "", note: "" });
      showToast(lang === "ar" ? "تم تعديل الرصيد ✨" : "Balance adjusted ✨");
      await load();
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setBusy(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="admin-clients-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="admin-clients-page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
            {lang === "ar" ? "إدارة العملاء" : "Clients"}
          </h1>
          <p className="text-stone-600 mt-1 text-sm flex items-center gap-1.5">
            <Users size={14} />
            {clients.length} {lang === "ar" ? "عميل مُسجّل" : "registered clients"}
          </p>
        </div>
      </div>

      {toast && (
        <div data-testid="admin-toast" className="bg-emerald-50 border border-emerald-200 rounded-2xl p-3.5 text-sm text-emerald-900 flex items-center gap-2">
          <Check size={16} className="text-emerald-700" /> {toast}
        </div>
      )}
      {error && (
        <div data-testid="admin-error" className="bg-red-50 border border-red-200 rounded-2xl p-3.5 text-sm text-red-800 flex items-center gap-2">
          <X size={16} className="text-red-600" /> {error}
        </div>
      )}

      {/* Filters */}
      <Card className="rounded-2xl border-stone-200">
        <CardContent className="p-4 flex flex-col md:flex-row gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute top-1/2 -translate-y-1/2 start-3 text-stone-400" />
            <Input
              data-testid="admin-search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={lang === "ar" ? "ابحث بالاسم، البريد، الشركة..." : "Search name, email, company..."}
              className="ps-9 h-11 rounded-xl"
            />
          </div>
          <Select value={planFilter} onValueChange={setPlanFilter}>
            <SelectTrigger className="w-full md:w-44 h-11 rounded-xl" data-testid="filter-plan">
              <SelectValue placeholder={lang === "ar" ? "كل الباقات" : "All plans"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{lang === "ar" ? "كل الباقات" : "All plans"}</SelectItem>
              <SelectItem value="GROWTH">Growth</SelectItem>
              <SelectItem value="PRO">Pro</SelectItem>
              <SelectItem value="ENTERPRISE">Enterprise</SelectItem>
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-full md:w-44 h-11 rounded-xl" data-testid="filter-status">
              <SelectValue placeholder={lang === "ar" ? "كل الحالات" : "All statuses"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{lang === "ar" ? "كل الحالات" : "All statuses"}</SelectItem>
              <SelectItem value="ACTIVE">Active</SelectItem>
              <SelectItem value="TRIALING">Trialing</SelectItem>
              <SelectItem value="PAST_DUE">Past due</SelectItem>
              <SelectItem value="CANCELED">Canceled</SelectItem>
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      {/* Data table */}
      <Card className="rounded-2xl border-stone-200 overflow-hidden">
        <div className="overflow-x-auto">
          <Table data-testid="clients-table">
            <TableHeader>
              <TableRow className="bg-stone-50 hover:bg-stone-50">
                <SortableHead label={lang === "ar" ? "الاسم" : "Name"} col="name" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                <SortableHead label={lang === "ar" ? "البريد" : "Email"} col="email" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} />
                <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "الباقة" : "Plan"}</TableHead>
                <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">{lang === "ar" ? "الحالة" : "Status"}</TableHead>
                <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600">Chatwoot ID</TableHead>
                <SortableHead label={lang === "ar" ? "الرصيد (ر.ع)" : "Balance (OMR)"} col="balance_omr" sortBy={sortBy} sortDir={sortDir} onSort={toggleSort} align="end" />
                <TableHead className="text-xs font-bold uppercase tracking-wider text-stone-600 text-end">{lang === "ar" ? "إجراءات" : "Actions"}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-10 text-stone-500 text-sm">
                    {lang === "ar" ? "لا توجد نتائج" : "No results"}
                  </TableCell>
                </TableRow>
              ) : (
                filtered.map((c) => (
                  <TableRow key={c.id} data-testid={`client-row-${c.id}`} className={!c.is_active ? "opacity-60" : ""}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        <div className="w-9 h-9 rounded-full bg-gradient-to-br from-emerald-700 to-emerald-900 flex items-center justify-center font-heading font-bold text-white text-sm">
                          {c.name?.[0]?.toUpperCase() || "?"}
                        </div>
                        <div>
                          <div className="font-semibold text-stone-900 text-sm">{c.name || "—"}</div>
                          {c.company_name && <div className="text-xs text-stone-500">{c.company_name}</div>}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-stone-700">{c.email}</TableCell>
                    <TableCell>
                      <Badge variant="outline" className={`text-[10px] font-bold ${PLAN_STYLES[c.plan_tier] || PLAN_STYLES["—"]}`}>
                        {c.plan_tier}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className={`text-[10px] font-bold ${STATUS_STYLES[c.status] || STATUS_STYLES["—"]}`}>
                        {!c.is_active ? (lang === "ar" ? "معلّق" : "Suspended") : c.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs font-mono text-stone-600">
                      {c.chatwoot_account_id || "—"}
                    </TableCell>
                    <TableCell className="text-end">
                      <div className="font-bold text-stone-900">{c.balance_omr.toFixed(2)}</div>
                      <div className="text-[10px] text-stone-400">
                        {c.promotional_credits.toLocaleString(lang === "ar" ? "ar-EG" : "en-US")} {lang === "ar" ? "رسالة" : "msgs"}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 justify-end">
                        <Button
                          data-testid={`action-credit-${c.id}`}
                          variant="outline"
                          size="sm"
                          onClick={() => setCreditDialog({ open: true, client: c, amount: "", note: "" })}
                          className="rounded-lg h-8 px-2.5 border-stone-200 hover:border-emerald-700 hover:text-emerald-800"
                          title={lang === "ar" ? "تعديل الرصيد" : "Adjust balance"}
                        >
                          <Wallet size={14} />
                        </Button>
                        <Button
                          data-testid={`action-toggle-${c.id}`}
                          variant="outline"
                          size="sm"
                          onClick={() => toggleStatus(c)}
                          disabled={busy?.id === c.id}
                          className={`rounded-lg h-8 px-2.5 ${
                            c.is_active
                              ? "border-stone-200 hover:border-amber-500 hover:text-amber-700"
                              : "border-emerald-200 text-emerald-700 hover:bg-emerald-50"
                          }`}
                          title={c.is_active ? (lang === "ar" ? "تعليق" : "Suspend") : (lang === "ar" ? "تفعيل" : "Activate")}
                        >
                          {busy?.id === c.id && busy?.action === "status" ? (
                            <Loader2 className="animate-spin" size={14} />
                          ) : c.is_active ? (
                            <Pause size={14} />
                          ) : (
                            <Play size={14} />
                          )}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </Card>

      {/* Credit / debit dialog */}
      <Dialog open={creditDialog.open} onOpenChange={(o) => !o && setCreditDialog({ open: false, client: null, amount: "", note: "" })}>
        <DialogContent className="rounded-3xl" data-testid="credit-dialog">
          <DialogHeader>
            <DialogTitle className="font-heading">
              {lang === "ar" ? "تعديل رصيد المحفظة يدوياً" : "Manually adjust wallet balance"}
            </DialogTitle>
            <DialogDescription>
              {creditDialog.client && (
                <>
                  {lang === "ar" ? "العميل" : "Client"}: <span className="font-semibold text-stone-900">{creditDialog.client.name}</span>
                  {" · "}
                  {lang === "ar" ? "الرصيد الحالي" : "Current"}: <span className="font-mono">{creditDialog.client.balance_omr.toFixed(2)} {lang === "ar" ? "ر.ع" : "OMR"}</span>
                </>
              )}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div>
              <label className="text-sm font-medium text-stone-700 mb-1.5 block">
                {lang === "ar" ? "المبلغ (موجب للإضافة، سالب للخصم)" : "Amount (positive to credit, negative to debit)"}
              </label>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCreditDialog((d) => ({ ...d, amount: String(-Math.abs(parseFloat(d.amount) || 0)) }))}
                  className="rounded-xl"
                  data-testid="amount-negate"
                >
                  <Minus size={14} />
                </Button>
                <Input
                  data-testid="credit-amount"
                  type="number"
                  step="0.01"
                  value={creditDialog.amount}
                  onChange={(e) => setCreditDialog((d) => ({ ...d, amount: e.target.value }))}
                  placeholder="12.50"
                  className="h-11 rounded-xl text-center font-mono"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setCreditDialog((d) => ({ ...d, amount: String(Math.abs(parseFloat(d.amount) || 0)) }))}
                  className="rounded-xl"
                  data-testid="amount-positive"
                >
                  <Plus size={14} />
                </Button>
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-stone-700 mb-1.5 block">
                {lang === "ar" ? "ملاحظة (اختياري)" : "Note (optional)"}
              </label>
              <Input
                data-testid="credit-note"
                value={creditDialog.note}
                onChange={(e) => setCreditDialog((d) => ({ ...d, note: e.target.value }))}
                placeholder={lang === "ar" ? "سبب التعديل..." : "Adjustment reason..."}
                className="h-11 rounded-xl"
              />
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setCreditDialog({ open: false, client: null, amount: "", note: "" })}
              className="rounded-xl"
            >
              {lang === "ar" ? "إلغاء" : "Cancel"}
            </Button>
            <Button
              data-testid="credit-submit"
              onClick={submitCredit}
              disabled={busy?.action === "credit"}
              className="rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white"
            >
              {busy?.action === "credit" ? <Loader2 className="animate-spin me-2" size={14} /> : null}
              {lang === "ar" ? "تطبيق" : "Apply"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

const SortableHead = ({ label, col, sortBy, sortDir, onSort, align = "start" }) => (
  <TableHead className={`text-xs font-bold uppercase tracking-wider text-stone-600 text-${align}`}>
    <button
      onClick={() => onSort(col)}
      className={`inline-flex items-center gap-1 hover:text-emerald-800 ${sortBy === col ? "text-emerald-800" : ""}`}
      data-testid={`sort-${col}`}
    >
      {label}
      <ArrowUpDown size={12} className={sortBy === col ? "" : "opacity-50"} />
    </button>
  </TableHead>
);
