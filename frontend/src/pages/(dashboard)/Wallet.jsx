import React, { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  Wallet as WalletIcon,
  Sparkles,
  MessageSquare,
  Check,
  Loader2,
  TrendingUp,
  Receipt,
  ArrowDownToLine,
  Zap,
  Info,
} from "lucide-react";

export default function Wallet() {
  const { lang } = useLang();
  const [data, setData] = useState(null);
  const [packages, setPackages] = useState([]);
  const [pricePerMsg, setPricePerMsg] = useState(0.025);
  const [error, setError] = useState("");
  const [topping, setTopping] = useState(null);
  const [toast, setToast] = useState("");

  const load = async () => {
    try {
      const [w, p] = await Promise.all([api.get("/me/wallet"), api.get("/wallet/packages")]);
      setData(w.data);
      setPackages(p.data.packages);
      setPricePerMsg(p.data.price_per_message_omr);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onTopup = async (pkgId) => {
    setTopping(pkgId);
    setError("");
    try {
      const { data: r } = await api.post("/me/wallet/topup", { package_id: pkgId });
      // If real gateway (Thawani), redirect to its checkout page
      if (r.payment_url) {
        window.location.href = r.payment_url;
        return;
      }
      // Mock mode: instantly credited
      setData((d) => ({
        ...d,
        wallet: r.wallet,
        estimated_messages_remaining: r.estimated_messages_remaining,
        transactions: [r.transaction, ...(d?.transactions || [])],
      }));
      setToast(lang === "ar" ? "تم شحن المحفظة بنجاح ✨" : "Wallet topped up successfully ✨");
      setTimeout(() => setToast(""), 4000);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    } finally {
      setTopping(null);
    }
  };

  // After redirect back from Thawani, show success/cancel toast
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const status = params.get("topup");
    if (status === "success") {
      setToast(lang === "ar" ? "💚 شكراً! تم استلام الدفعة، الرصيد سيُحدّث خلال ثوانٍ." : "💚 Thanks! Payment received, balance will update shortly.");
      setTimeout(() => setToast(""), 6000);
      // Soft-refresh wallet to pick up webhook credit
      setTimeout(load, 3000);
      setTimeout(load, 8000);
      window.history.replaceState({}, "", "/dashboard/wallet");
    } else if (status === "cancelled") {
      setError(lang === "ar" ? "تم إلغاء العملية. لم يُخصم أي مبلغ." : "Payment cancelled. No charge was made.");
      window.history.replaceState({}, "", "/dashboard/wallet");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const balance = data?.wallet?.balance_omr ?? 0;
  const credits = data?.wallet?.promotional_credits ?? 0;
  const estimated = data?.estimated_messages_remaining ?? 0;

  const dateFmt = useMemo(
    () => (iso) =>
      iso
        ? new Date(iso).toLocaleDateString(lang === "ar" ? "ar-OM" : "en-OM", {
            year: "numeric",
            month: "short",
            day: "numeric",
          })
        : "—",
    [lang]
  );

  if (!data || packages.length === 0) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="wallet-loading">
        <Loader2 className="animate-spin text-emerald-700" size={32} />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="wallet-page">
      <div>
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "المحفظة ورصيد الرسائل" : "Wallet & Credits"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar"
            ? "اشحن محفظتك لإرسال حملات واتساب الترويجية لعملائك. نحن ندفع لـ Meta نيابةً عنك."
            : "Top up your wallet to send WhatsApp promotional campaigns. We pay Meta on your behalf."}
        </p>
      </div>

      {toast && (
        <div data-testid="wallet-toast" className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-sm text-emerald-900 flex items-center gap-2">
          <Check size={16} className="text-emerald-700" />
          {toast}
        </div>
      )}
      {error && (
        <div data-testid="wallet-error" className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-800">
          {error}
        </div>
      )}

      {/* Balance + Messages estimate */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <Card data-testid="balance-card" className="rounded-3xl bg-emerald-900 text-white border-emerald-900 relative overflow-hidden">
          <div className="absolute -top-20 -end-20 w-72 h-72 bg-emerald-700 rounded-full blur-3xl opacity-40"></div>
          <CardHeader className="relative pb-2">
            <CardTitle className="text-sm font-semibold text-emerald-100/80 flex items-center gap-2">
              <WalletIcon size={16} className="text-amber-400" />
              {lang === "ar" ? "رصيد المحفظة" : "Wallet balance"}
            </CardTitle>
          </CardHeader>
          <CardContent className="relative">
            <div className="flex items-baseline gap-2 mb-2">
              <span data-testid="balance-amount" className="font-heading text-5xl font-bold tracking-tight">
                {balance.toFixed(2)}
              </span>
              <span className="text-amber-300 font-semibold">{lang === "ar" ? "ر.ع" : "OMR"}</span>
            </div>
            <p className="text-xs text-emerald-100/70">
              {data.wallet?.last_topup_at
                ? `${lang === "ar" ? "آخر شحن" : "Last top-up"}: ${dateFmt(data.wallet.last_topup_at)}`
                : lang === "ar"
                ? "لم تقم بأي شحن حتى الآن"
                : "No top-ups yet"}
            </p>
          </CardContent>
        </Card>

        <Card data-testid="messages-estimate-card" className="rounded-3xl border-stone-200">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-semibold text-stone-600 flex items-center gap-2">
              <MessageSquare size={16} className="text-emerald-700" />
              {lang === "ar" ? "تقدير الرسائل المتبقية" : "Estimated messages remaining"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2 mb-3">
              <span data-testid="estimate-amount" className="font-heading text-5xl font-bold text-stone-900">
                {estimated.toLocaleString(lang === "ar" ? "ar-EG" : "en-US")}
              </span>
              <span className="text-sm text-stone-500">{lang === "ar" ? "رسالة" : "msgs"}</span>
            </div>
            <p className="text-xs text-stone-500 flex items-center gap-1.5">
              <Info size={12} />
              {lang === "ar"
                ? `محسوبة على أساس ${pricePerMsg} ر.ع لكل رسالة ترويجية`
                : `Based on ${pricePerMsg} OMR per promotional message`}
            </p>
            <div className="mt-3 flex items-center gap-2 text-xs">
              <Zap size={12} className="text-amber-600" />
              <span className="text-stone-600">
                <span className="font-semibold text-stone-900">{credits.toLocaleString(lang === "ar" ? "ar-EG" : "en-US")}</span>{" "}
                {lang === "ar" ? "رصيد مدفوع مسبقاً" : "pre-paid credits"}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Solution Partner explainer */}
      <Card className="rounded-3xl border-amber-200 bg-amber-50/50">
        <CardContent className="p-5 flex items-start gap-3">
          <div className="flex-shrink-0 w-10 h-10 rounded-xl bg-amber-100 flex items-center justify-center">
            <Sparkles size={18} className="text-amber-700" />
          </div>
          <div className="text-sm text-stone-700 leading-relaxed">
            <p className="font-semibold text-stone-900 mb-1">
              {lang === "ar" ? "كيف يعمل الفوترة؟" : "How billing works"}
            </p>
            <p className="text-stone-600">
              {lang === "ar"
                ? "سوشال هَب هو شريك حلول معتمد. أنت تشحن محفظتك بالعملة المحلية (ر.ع)، ونحن نتولى الدفع لـ Meta عند إرسال كل رسالة ترويجية. سعر الرسالة الواحدة: "
                : "SocialHub is a certified Solution Partner. You top up your wallet in OMR; we pay Meta on every promotional message. Per-message rate: "}
              <span className="font-bold text-emerald-800">{pricePerMsg} {lang === "ar" ? "ر.ع" : "OMR"}</span>.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Top-up packages */}
      <div>
        <h2 className="font-heading text-xl md:text-2xl font-bold text-stone-900 mb-1">
          {lang === "ar" ? "اشحن محفظتك" : "Top up your wallet"}
        </h2>
        <p className="text-stone-500 text-sm mb-6">
          {lang === "ar" ? "اختر باقة الشحن المناسبة. الرصيد لا ينتهي." : "Pick a package — credits never expire."}
        </p>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {packages.map((p) => {
            const highlighted = p.id === "pro";
            return (
              <Card
                key={p.id}
                data-testid={`topup-card-${p.id}`}
                className={`rounded-3xl transition-all hover:-translate-y-1 hover:shadow-xl ${
                  highlighted
                    ? "border-2 border-emerald-700 shadow-md relative"
                    : "border-stone-200"
                }`}
              >
                {highlighted && (
                  <div className="absolute -top-3 inset-x-0 flex justify-center">
                    <Badge className="bg-amber-500 text-stone-900 hover:bg-amber-500 shadow-sm">
                      <Sparkles size={12} className="me-1" />
                      {lang === "ar" ? "الأفضل قيمة" : "Best value"}
                    </Badge>
                  </div>
                )}
                <CardHeader className={highlighted ? "pt-6" : ""}>
                  <CardTitle className="font-heading text-lg font-bold text-stone-900 flex items-center justify-between">
                    {lang === "ar" ? p.name_ar : p.name_en}
                    <span className="text-xs font-semibold text-stone-400">#{p.id}</span>
                  </CardTitle>
                  <CardDescription className="text-stone-500">
                    <span className="font-bold text-2xl text-emerald-800">
                      {p.messages.toLocaleString(lang === "ar" ? "ar-EG" : "en-US")}
                    </span>{" "}
                    {lang === "ar" ? "رسالة ترويجية" : "promotional messages"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="mb-5">
                    <div className="flex items-baseline gap-1">
                      <span className="font-heading text-3xl font-bold text-stone-900">{p.price_omr}</span>
                      <span className="text-sm text-stone-500">{lang === "ar" ? "ر.ع" : "OMR"}</span>
                    </div>
                    <p className="text-[11px] text-stone-400 mt-1">
                      {(p.price_omr / p.messages).toFixed(3)} {lang === "ar" ? "ر.ع/رسالة" : "OMR/msg"}
                    </p>
                  </div>
                  <Button
                    data-testid={`topup-btn-${p.id}`}
                    onClick={() => onTopup(p.id)}
                    disabled={topping === p.id}
                    className={`w-full rounded-xl h-11 font-semibold ${
                      highlighted
                        ? "bg-emerald-800 hover:bg-emerald-900 text-white"
                        : "bg-stone-900 hover:bg-emerald-900 text-white"
                    }`}
                  >
                    {topping === p.id ? (
                      <>
                        <Loader2 className="animate-spin me-2" size={16} />
                        {lang === "ar" ? "جاري المعالجة..." : "Processing..."}
                      </>
                    ) : (
                      <>
                        <ArrowDownToLine size={16} className="me-2" />
                        {lang === "ar" ? "اشحن الآن" : "Top up now"}
                      </>
                    )}
                  </Button>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>

      {/* Recent transactions */}
      <Card data-testid="transactions-card" className="rounded-3xl border-stone-200">
        <CardHeader>
          <CardTitle className="text-base font-heading font-bold text-stone-900 flex items-center gap-2">
            <Receipt size={18} className="text-emerald-700" />
            {lang === "ar" ? "آخر العمليات" : "Recent transactions"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {data.transactions.length === 0 ? (
            <div className="text-center py-10 text-stone-500 text-sm">
              <TrendingUp size={28} className="mx-auto mb-2 text-stone-300" />
              {lang === "ar" ? "لا توجد عمليات بعد. ابدأ بأول عملية شحن!" : "No transactions yet. Start with your first top-up!"}
            </div>
          ) : (
            <div className="divide-y divide-stone-100">
              {data.transactions.map((tx) => (
                <div key={tx.id} className="flex items-center justify-between py-3" data-testid={`txn-${tx.id}`}>
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-xl bg-emerald-50 flex items-center justify-center">
                      <ArrowDownToLine size={16} className="text-emerald-700" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-stone-900">
                        {lang === "ar" ? "شحن محفظة" : "Wallet top-up"} · {tx.package_name}
                      </p>
                      <p className="text-xs text-stone-500">
                        {tx.messages.toLocaleString(lang === "ar" ? "ar-EG" : "en-US")}{" "}
                        {lang === "ar" ? "رسالة" : "msgs"} · {dateFmt(tx.created_at)}
                      </p>
                    </div>
                  </div>
                  <div className="text-end">
                    <p className="font-bold text-emerald-800">+{tx.amount_omr} {lang === "ar" ? "ر.ع" : "OMR"}</p>
                    <Badge variant="outline" className="text-[10px] border-emerald-200 text-emerald-800 bg-emerald-50 mt-0.5">
                      {tx.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
