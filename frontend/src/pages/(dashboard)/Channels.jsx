import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useLang } from "@/contexts/LanguageContext";
import { api, formatApiErrorDetail } from "@/contexts/AuthContext";
import {
  loadFacebookSDK,
  launchWhatsAppSignup,
  isFacebookConfigured,
} from "@/lib/facebook";
import {
  MessageCircle,
  Instagram,
  Facebook,
  Mail,
  Globe,
  Check,
  Loader2,
  Clock,
  ShieldCheck,
  Sparkles,
  ExternalLink,
  X,
  Info,
} from "lucide-react";

const PROVIDER_META = {
  whatsapp: { icon: MessageCircle, color: "bg-emerald-500", brand: "WhatsApp" },
  instagram: { icon: Instagram, color: "bg-gradient-to-tr from-pink-500 to-amber-500", brand: "Instagram" },
  facebook: { icon: Facebook, color: "bg-blue-600", brand: "Facebook Messenger" },
  email: { icon: Mail, color: "bg-amber-600", brand: "Email" },
  webchat: { icon: Globe, color: "bg-stone-700", brand: "Web Chat" },
};

export default function Channels() {
  const { lang } = useLang();
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [fbReady, setFbReady] = useState(false);
  const [mockMode, setMockMode] = useState(true);

  useEffect(() => {
    isFacebookConfigured().then((b) => setMockMode(!b)).catch(() => setMockMode(true));
  }, []);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get("/me/channels");
        setChannels(data.channels || []);
      } catch (e) {
        setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
      } finally {
        setLoading(false);
      }
    })();
    // Preload SDK if Meta is configured on the backend
    (async () => {
      try {
        if (await isFacebookConfigured()) {
          await loadFacebookSDK();
          setFbReady(true);
        }
      } catch (_) { /* ignore */ }
    })();
  }, []);

  const whatsapp = channels.find((c) => c.provider === "whatsapp");

  const connectWhatsApp = async () => {
    setError("");
    setConnecting(true);
    try {
      const metaEnabled = await isFacebookConfigured();
      let session;
      if (metaEnabled) {
        // Real FB Embedded Signup flow
        session = await launchWhatsAppSignup();
      } else {
        // Mock flow (no Meta credentials yet) — simulate user completing signup
        await new Promise((r) => setTimeout(r, 1500));
        session = {
          waba_id: "1234567890123456",
          phone_number_id: "987654321098765",
          business_id: "5566778899001122",
          code: null,
        };
      }
      // Hit the real provisioning endpoint — backend handles both modes
      const payload = {
        waba_id: session.waba_id,
        phone_number_id: session.phone_number_id,
        business_id: session.business_id,
        code: session.code,
      };
      const { data } = await api.post("/whatsapp/connect", payload);
      setChannels((cs) => [...cs.filter((c) => c.provider !== "whatsapp"), data.channel]);
      setToast(
        lang === "ar"
          ? "🎉 تم ربط رقم واتساب بنجاح!"
          : "🎉 WhatsApp number connected successfully!"
      );
      setTimeout(() => setToast(""), 5000);
      // Refresh mock indicator
      setMockMode(!metaEnabled);
    } catch (e) {
      const msg = e?.message === "USER_CANCELLED"
        ? (lang === "ar" ? "تم إلغاء العملية." : "Signup cancelled.")
        : formatApiErrorDetail(e.response?.data?.detail) || e.message;
      setError(msg);
    } finally {
      setConnecting(false);
    }
  };

  const disconnectWhatsApp = async () => {
    if (!window.confirm(lang === "ar" ? "هل أنت متأكد من فصل واتساب؟" : "Disconnect WhatsApp?")) return;
    try {
      await api.delete("/me/channels/whatsapp");
      setChannels((cs) => cs.filter((c) => c.provider !== "whatsapp"));
      setToast(lang === "ar" ? "تم فصل القناة." : "Channel disconnected.");
      setTimeout(() => setToast(""), 3000);
    } catch (e) {
      setError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
    }
  };

  return (
    <div className="space-y-6" data-testid="channels-page">
      <div>
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900">
          {lang === "ar" ? "قنوات التواصل" : "Channels"}
        </h1>
        <p className="text-stone-600 mt-1 text-sm">
          {lang === "ar"
            ? "اربط منصات التواصل بحسابك. كل المحادثات ستظهر في صندوق واحد."
            : "Connect your messaging platforms. All chats land in one unified inbox."}
        </p>
      </div>

      {toast && (
        <div data-testid="channels-toast" className="bg-emerald-50 border border-emerald-200 rounded-2xl p-4 text-sm text-emerald-900 flex items-center gap-2">
          <Check size={16} className="text-emerald-700" />
          {toast}
        </div>
      )}
      {error && (
        <div data-testid="channels-error" className="bg-red-50 border border-red-200 rounded-2xl p-4 text-sm text-red-800 flex items-start gap-2">
          <X size={16} className="text-red-600 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}

      {/* WhatsApp - HERO connect card */}
      {!whatsapp ? (
        <WhatsAppConnectCard
          onConnect={connectWhatsApp}
          connecting={connecting}
          fbReady={fbReady}
          mock={mockMode}
          lang={lang}
        />
      ) : (
        <WhatsAppConnectedCard channel={whatsapp} onDisconnect={disconnectWhatsApp} lang={lang} />
      )}

      {/* Other channels - placeholders */}
      <div>
        <h2 className="font-heading text-lg font-bold text-stone-900 mb-3">
          {lang === "ar" ? "قنوات أخرى" : "Other channels"}
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {["instagram", "facebook", "email", "webchat"].map((p) => {
            const meta = PROVIDER_META[p];
            const Icon = meta.icon;
            return (
              <Card key={p} data-testid={`channel-${p}-card`} className="rounded-2xl border-stone-200 hover:border-stone-300 transition-colors">
                <CardContent className="p-5 flex items-center gap-4">
                  <div className={`w-12 h-12 rounded-2xl ${meta.color} flex items-center justify-center text-white flex-shrink-0`}>
                    <Icon size={20} />
                  </div>
                  <div className="flex-1">
                    <p className="font-semibold text-stone-900">{meta.brand}</p>
                    <p className="text-xs text-stone-500">
                      {lang === "ar" ? "قريباً — متاح في المرحلة القادمة" : "Coming soon — next release"}
                    </p>
                  </div>
                  <Badge variant="outline" className="text-[10px] border-stone-200 text-stone-500 bg-stone-50">
                    {lang === "ar" ? "قريباً" : "Soon"}
                  </Badge>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* WhatsApp connect card (NOT YET CONNECTED)                          */
/* ------------------------------------------------------------------ */
const WhatsAppConnectCard = ({ onConnect, connecting, fbReady, mock, lang }) => (
  <Card
    data-testid="whatsapp-connect-card"
    className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-emerald-900 via-emerald-800 to-emerald-900 text-white border-emerald-900"
  >
    <div className="absolute -top-32 -end-32 w-96 h-96 bg-emerald-600 rounded-full blur-3xl opacity-40"></div>
    <div className="absolute -bottom-32 -start-12 w-72 h-72 bg-amber-500/20 rounded-full blur-3xl"></div>

    <div className="relative grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-8 p-8 md:p-10">
      <div>
        <div className="inline-flex items-center gap-2 bg-white/10 backdrop-blur border border-white/20 rounded-full px-3 py-1.5 mb-5">
          <div className="w-7 h-7 rounded-full bg-emerald-500 flex items-center justify-center">
            <MessageCircle size={14} className="text-white" />
          </div>
          <span className="text-xs font-semibold uppercase tracking-wider text-emerald-100">WhatsApp Business</span>
        </div>

        <h2 className="font-heading text-3xl md:text-4xl font-bold mb-3 leading-tight">
          {lang === "ar" ? "اربط واتساب في ٣ دقائق" : "Connect WhatsApp in 3 minutes"}
        </h2>
        <p className="text-emerald-100/80 leading-relaxed mb-6 max-w-xl">
          {lang === "ar"
            ? "ربط رسمي عبر Meta Business — احصل على رقم واتساب موثّق بالعلامة الخضراء، حملات ترويجية، وردود تلقائية. كل ذلك بنقرة واحدة."
            : "Official Meta Business onboarding — get a verified green-checkmark WhatsApp number, promotional campaigns, and auto-replies. All with one click."}
        </p>

        <ul className="space-y-2.5 mb-7">
          {[
            lang === "ar" ? "رقم WhatsApp Business موثّق رسمياً" : "Officially verified WhatsApp Business number",
            lang === "ar" ? "لا تحتاج لتطبيقات أو رموز QR" : "No app installs or QR codes required",
            lang === "ar" ? "تظهر الرسائل فوراً في صندوقك الموحّد" : "Messages flow into your unified inbox immediately",
          ].map((t, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-emerald-50">
              <div className="flex-shrink-0 w-5 h-5 rounded-full bg-emerald-700/40 flex items-center justify-center mt-0.5">
                <Check size={12} className="text-amber-300" strokeWidth={3} />
              </div>
              {t}
            </li>
          ))}
        </ul>

        <Button
          data-testid="connect-whatsapp-btn"
          onClick={onConnect}
          disabled={connecting}
          size="lg"
          className="bg-amber-500 hover:bg-amber-400 text-stone-900 rounded-2xl px-7 h-14 text-base font-bold shadow-lg shadow-amber-900/30 hover:-translate-y-1 transition-all"
        >
          {connecting ? (
            <>
              <Loader2 className="animate-spin me-2" size={18} />
              {lang === "ar" ? "جاري الربط..." : "Connecting..."}
            </>
          ) : (
            <>
              <MessageCircle size={18} className="me-2" />
              {lang === "ar" ? "اربط واتساب الآن" : "Connect WhatsApp now"}
            </>
          )}
        </Button>

        {mock && (
          <p className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-amber-200/80 bg-amber-500/10 border border-amber-400/30 rounded-full px-3 py-1">
            <Info size={11} />
            {lang === "ar"
              ? "وضع تجريبي: ضع REACT_APP_FACEBOOK_APP_ID و REACT_APP_WA_CONFIG_ID لتفعيل التدفق الحقيقي."
              : "Demo mode: set REACT_APP_FACEBOOK_APP_ID and REACT_APP_WA_CONFIG_ID to enable the real flow."}
          </p>
        )}
      </div>

      {/* Solution Partner explainer */}
      <div className="bg-white/5 backdrop-blur border border-white/10 rounded-3xl p-6 self-start">
        <div className="flex items-center gap-2 mb-3">
          <div className="w-9 h-9 rounded-xl bg-amber-500/20 border border-amber-400/30 flex items-center justify-center">
            <ShieldCheck size={18} className="text-amber-300" />
          </div>
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-amber-300">
              {lang === "ar" ? "شريك حلول معتمد" : "Solution Partner"}
            </p>
            <p className="text-xs text-emerald-100/70">Tech Provider · Meta</p>
          </div>
        </div>
        <p className="text-sm text-emerald-50/90 leading-relaxed mb-4">
          {lang === "ar"
            ? "هذا الربط يضيف رقمك مباشرة تحت حساب «سوشال هَب» كـ Tech Provider معتمد لدى Meta. لست بحاجة لإنشاء حساب Meta Developer منفصل."
            : "This connection adds your number directly under SocialHub's account as Meta's certified Tech Provider. You don't need to set up a Meta Developer account yourself."}
        </p>
        <div className="space-y-2">
          {[
            { icon: Clock, label: lang === "ar" ? "≈ ٣ دقائق" : "≈ 3 minutes" },
            { icon: ShieldCheck, label: lang === "ar" ? "آمن — لا نطّلع على محادثاتك" : "Secure — we don't read your chats" },
            { icon: Sparkles, label: lang === "ar" ? "نتولى الدفع لـ Meta نيابةً عنك" : "We pay Meta on your behalf" },
          ].map((it, i) => (
            <div key={i} className="flex items-center gap-2 text-xs text-emerald-100/80">
              <it.icon size={12} className="text-amber-300 flex-shrink-0" />
              {it.label}
            </div>
          ))}
        </div>
      </div>
    </div>
  </Card>
);

/* ------------------------------------------------------------------ */
/* WhatsApp connected state                                            */
/* ------------------------------------------------------------------ */
const WhatsAppConnectedCard = ({ channel, onDisconnect, lang }) => {
  const connectedAt = channel.connected_at
    ? new Date(channel.connected_at).toLocaleDateString(lang === "ar" ? "ar-OM" : "en-OM", {
        year: "numeric",
        month: "long",
        day: "numeric",
      })
    : "—";

  return (
    <Card data-testid="whatsapp-connected-card" className="rounded-3xl border-emerald-200 bg-white overflow-hidden">
      <CardHeader className="border-b border-stone-100 bg-emerald-50/30">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-emerald-500 flex items-center justify-center shadow-sm">
              <MessageCircle size={22} className="text-white" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <CardTitle className="font-heading text-lg font-bold text-stone-900">WhatsApp Business</CardTitle>
                <Badge className="bg-emerald-700 text-white hover:bg-emerald-700">
                  <Check size={11} className="me-1" strokeWidth={3} />
                  {lang === "ar" ? "متصل" : "Connected"}
                </Badge>
              </div>
              <CardDescription className="text-stone-500 mt-0.5">
                {lang === "ar" ? "تم الربط في" : "Connected on"} {connectedAt}
              </CardDescription>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-6">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          <DataField
            label={lang === "ar" ? "رقم الهاتف" : "Phone number"}
            value={channel.phone_number}
            testId="wa-phone-value"
            mono
          />
          <DataField
            label={lang === "ar" ? "معرّف WABA" : "WABA ID"}
            value={channel.waba_id}
            testId="wa-waba-value"
            mono
          />
          <DataField
            label={lang === "ar" ? "اسم العرض" : "Display name"}
            value={channel.display_name || "—"}
            testId="wa-display-value"
          />
          <DataField
            label={lang === "ar" ? "Phone Number ID" : "Phone Number ID"}
            value={channel.phone_number_id || "—"}
            testId="wa-pnid-value"
            mono
          />
          <DataField
            label={lang === "ar" ? "Business ID" : "Business ID"}
            value={channel.business_id || "—"}
            testId="wa-biz-value"
            mono
          />
          <div className="md:col-span-1 flex items-end">
            <Button
              data-testid="disconnect-whatsapp-btn"
              variant="outline"
              onClick={onDisconnect}
              className="w-full rounded-xl border-red-200 text-red-700 hover:bg-red-50 hover:border-red-300"
            >
              <X size={14} className="me-2" />
              {lang === "ar" ? "فصل القناة" : "Disconnect"}
            </Button>
          </div>
        </div>

        <div className="mt-6 flex items-start gap-2 p-4 bg-emerald-50/60 border border-emerald-100 rounded-2xl text-xs text-emerald-900">
          <ShieldCheck size={14} className="text-emerald-700 mt-0.5 flex-shrink-0" />
          <p>
            {lang === "ar"
              ? "هذا الرقم مُسجّل تحت حساب «سوشال هَب» كـ Tech Provider لدى Meta. الرسائل ترسل عبر سوشال هَب، وسعر كل رسالة ترويجية يُخصم من محفظتك (٠.٠٢٥ ر.ع/رسالة)."
              : "This number is registered under SocialHub's account as Meta's Tech Provider. Messages route through SocialHub, and each promotional message is debited from your wallet (0.025 OMR/message)."}
          </p>
        </div>
      </CardContent>
    </Card>
  );
};

const DataField = ({ label, value, testId, mono = false }) => (
  <div>
    <div className="text-[11px] font-bold uppercase tracking-wider text-stone-500 mb-1.5">{label}</div>
    <div
      data-testid={testId}
      className={`text-sm text-stone-900 bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 truncate ${
        mono ? "font-mono" : "font-semibold"
      }`}
    >
      {value}
    </div>
  </div>
);
