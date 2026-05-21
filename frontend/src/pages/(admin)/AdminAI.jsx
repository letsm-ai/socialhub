import React, { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { useLang } from "@/contexts/LanguageContext";
import { api } from "@/contexts/AuthContext";
import { Bot, Plus, Trash2, Loader2, BookOpen, Sparkles, AlertCircle, Save, Stethoscope, Send, CheckCircle2, XCircle, Key, Zap, Eye, EyeOff, UserCheck } from "lucide-react";

export default function AdminAI() {
  const { lang } = useLang();
  const t = (a, e) => (lang === "ar" ? a : e);

  const [settings, setSettings] = useState(null);
  const [knowledge, setKnowledge] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [newItem, setNewItem] = useState({ title: "", content: "", lang: "both" });
  const [adding, setAdding] = useState(false);
  const [diag, setDiag] = useState(null);
  const [diagLoading, setDiagLoading] = useState(false);
  const [testInput, setTestInput] = useState(
    lang === "ar" ? "السلام عليكم، كم سعر الباقة؟" : "Hi, what's your pricing?"
  );
  const [testResult, setTestResult] = useState(null);
  const [testing, setTesting] = useState(false);
  const [openaiKeyDraft, setOpenaiKeyDraft] = useState("");
  const [showOpenaiKey, setShowOpenaiKey] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const [s, k] = await Promise.all([
        api.get("/admin/ai/settings"),
        api.get("/admin/ai/knowledge"),
      ]);
      setSettings(s.data);
      setKnowledge(k.data.items || []);
      setError("");
    } catch (e) {
      setError(e?.response?.data?.detail || "Failed to load");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    try {
      const payload = { ...settings };
      if (openaiKeyDraft.trim()) {
        payload.openai_api_key = openaiKeyDraft.trim();
      } else {
        delete payload.openai_api_key; // leave existing untouched
      }
      const { data } = await api.put("/admin/ai/settings", payload);
      setSettings(data);
      setOpenaiKeyDraft("");
      setError("");
    } catch (e) {
      setError(e?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const addKnowledge = async () => {
    if (!newItem.title.trim() || !newItem.content.trim()) return;
    setAdding(true);
    try {
      await api.post("/admin/ai/knowledge", newItem);
      setNewItem({ title: "", content: "", lang: "both" });
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || "Add failed");
    } finally {
      setAdding(false);
    }
  };

  const deleteKnowledge = async (id) => {
    if (!window.confirm(t("هل تريد حذف هذه المعلومة؟", "Delete this entry?"))) return;
    try {
      await api.delete(`/admin/ai/knowledge/${id}`);
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || "Delete failed");
    }
  };

  const runDiagnostics = async () => {
    setDiagLoading(true);
    try {
      const { data } = await api.get("/admin/ai/diagnostics");
      setDiag(data);
    } catch (e) {
      setError(e?.response?.data?.detail || "Diagnostics failed");
    } finally {
      setDiagLoading(false);
    }
  };

  const runTestReply = async () => {
    if (!testInput.trim()) return;
    setTesting(true);
    setTestResult(null);
    try {
      const { data } = await api.post("/admin/ai/test-reply", { text: testInput });
      setTestResult(data);
    } catch (e) {
      setTestResult({ action: "error", error: e?.response?.data?.detail || "Request failed" });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20 text-stone-500" data-testid="admin-ai-loading">
        <Loader2 className="animate-spin me-2" />
        {t("جاري التحميل...", "Loading...")}
      </div>
    );
  }

  if (!settings) return null;

  return (
    <div className="space-y-6" data-testid="admin-ai-page">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-stone-900 flex items-center gap-3">
            <Bot className="text-emerald-700" size={32} />
            {t("مساعد الذكاء الاصطناعي", "AI Assistant")}
          </h1>
          <p className="text-stone-600 mt-1 text-sm">
            {t(
              "البوت يرد آلياً على رسائل واتساب اعتماداً على المعلومات التي تغذّيه بها.",
              "The bot auto-replies to WhatsApp using only the knowledge you provide."
            )}
          </p>
        </div>
        <div className="flex items-center gap-3 bg-white rounded-2xl border border-stone-200 px-4 py-2.5">
          <Switch
            data-testid="ai-enabled-toggle"
            checked={!!settings.enabled}
            onCheckedChange={(v) => setSettings({ ...settings, enabled: v })}
          />
          <span className="text-sm font-semibold">
            {settings.enabled
              ? t("مفعّل", "Enabled")
              : t("معطّل", "Disabled")}
          </span>
        </div>
      </header>

      {error && (
        <div className="rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm p-3 flex gap-2">
          <AlertCircle size={16} /> {error}
        </div>
      )}

      {/* LLM Provider */}
      <Card data-testid="llm-provider-card">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Key size={18} className="text-emerald-700" />
            {t("مزوّد الذكاء الاصطناعي", "AI Provider")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid sm:grid-cols-2 gap-3">
            <button
              type="button"
              data-testid="provider-emergent"
              onClick={() => setSettings({ ...settings, llm_provider: "emergent" })}
              className={`text-start rounded-2xl border p-4 transition ${
                (settings.llm_provider || "emergent") === "emergent"
                  ? "border-emerald-700 bg-emerald-50 ring-2 ring-emerald-200"
                  : "border-stone-200 bg-white hover:border-stone-300"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="font-semibold flex items-center gap-2 text-stone-900">
                  <Zap size={16} className="text-emerald-700" />
                  {t("مفتاح Emergent (تلقائي)", "Emergent key (default)")}
                </span>
                {(settings.llm_provider || "emergent") === "emergent" && (
                  <Badge className="bg-emerald-700 text-white hover:bg-emerald-700 text-[10px]">
                    {t("الحالي", "ACTIVE")}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-stone-600 leading-relaxed">
                {t(
                  "يستخدم رصيد Emergent. مفتاح واحد لـ GPT-4o و Claude و Gemini.",
                  "Uses your Emergent balance. One key for GPT-4o, Claude, and Gemini."
                )}
              </p>
            </button>

            <button
              type="button"
              data-testid="provider-openai"
              onClick={() => setSettings({ ...settings, llm_provider: "openai" })}
              className={`text-start rounded-2xl border p-4 transition ${
                settings.llm_provider === "openai"
                  ? "border-emerald-700 bg-emerald-50 ring-2 ring-emerald-200"
                  : "border-stone-200 bg-white hover:border-stone-300"
              }`}
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="font-semibold flex items-center gap-2 text-stone-900">
                  <Key size={16} className="text-emerald-700" />
                  {t("مفتاح OpenAI الخاص فيك", "Your own OpenAI key")}
                </span>
                {settings.llm_provider === "openai" && (
                  <Badge className="bg-emerald-700 text-white hover:bg-emerald-700 text-[10px]">
                    {t("الحالي", "ACTIVE")}
                  </Badge>
                )}
              </div>
              <p className="text-xs text-stone-600 leading-relaxed">
                {t(
                  "الفوترة تذهب مباشرة إلى حسابك في OpenAI. تحكم كامل في الموديل والاستخدام.",
                  "Billing goes directly to your OpenAI account. Full control over model and usage."
                )}
              </p>
            </button>
          </div>

          {settings.llm_provider === "openai" && (
            <div className="rounded-2xl border border-stone-200 bg-stone-50/50 p-4 space-y-3">
              <Label className="text-stone-700">
                {t("مفتاح OpenAI API", "OpenAI API key")}{" "}
                <span className="text-stone-400 font-normal text-xs">
                  ({t("يبدأ بـ", "starts with")} <code>sk-</code>)
                </span>
              </Label>
              {settings.openai_api_key_preview ? (
                <div className="flex items-center gap-2 text-sm text-stone-600">
                  <CheckCircle2 size={14} className="text-emerald-600" />
                  {t("المفتاح محفوظ:", "Stored key:")}{" "}
                  <code className="bg-white border border-stone-200 px-2 py-0.5 rounded text-xs">
                    {settings.openai_api_key_preview}
                  </code>
                </div>
              ) : (
                <div className="flex items-center gap-2 text-sm text-amber-700">
                  <AlertCircle size={14} />
                  {t("لم يتم حفظ أي مفتاح بعد.", "No key stored yet.")}
                </div>
              )}
              <div className="relative">
                <Input
                  data-testid="openai-api-key-input"
                  type={showOpenaiKey ? "text" : "password"}
                  value={openaiKeyDraft}
                  onChange={(e) => setOpenaiKeyDraft(e.target.value)}
                  placeholder={
                    settings.openai_api_key_preview
                      ? t("اتركه فارغاً للإبقاء على المفتاح الحالي", "Leave blank to keep current key")
                      : "sk-proj-..."
                  }
                  className="pr-10 font-mono text-sm"
                  dir="ltr"
                />
                <button
                  type="button"
                  data-testid="toggle-openai-key-visibility"
                  onClick={() => setShowOpenaiKey((v) => !v)}
                  className="absolute end-2 top-1/2 -translate-y-1/2 text-stone-400 hover:text-stone-600"
                >
                  {showOpenaiKey ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              <p className="text-[11px] text-stone-500 leading-relaxed">
                {t(
                  "احصل على المفتاح من ",
                  "Get a key from "
                )}
                <a
                  href="https://platform.openai.com/api-keys"
                  target="_blank"
                  rel="noreferrer"
                  className="text-emerald-700 underline"
                >
                  platform.openai.com/api-keys
                </a>
                {t(
                  ". المفتاح يُحفظ مشفّراً في قاعدة البيانات ولا يُعرض كاملاً مرة أخرى.",
                  ". The key is stored privately and never displayed in full again."
                )}
              </p>
            </div>
          )}

          <div className="grid sm:grid-cols-2 gap-4 pt-2">
            <div>
              <Label className="text-stone-700 mb-2 block">
                {t("الموديل", "Model")}
              </Label>
              <select
                data-testid="ai-model-select"
                value={settings.model || "gpt-4o"}
                onChange={(e) => setSettings({ ...settings, model: e.target.value })}
                className="w-full border border-stone-300 rounded-lg px-3 py-2 text-sm bg-white"
                dir="ltr"
              >
                <option value="gpt-4o">gpt-4o ({t("متوازن", "balanced")})</option>
                <option value="gpt-4o-mini">gpt-4o-mini ({t("أسرع وأرخص", "fast & cheap")})</option>
                <option value="gpt-4-turbo">gpt-4-turbo</option>
                <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Personality */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Sparkles size={18} className="text-emerald-700" />
            {t("شخصية البوت", "Bot personality")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div>
            <Label className="text-stone-700 mb-2 block">
              {t("الشخصية (عربي)", "Persona (Arabic)")}
            </Label>
            <Textarea
              data-testid="persona-ar"
              value={settings.persona_ar || ""}
              onChange={(e) => setSettings({ ...settings, persona_ar: e.target.value })}
              rows={6}
              dir="rtl"
              className="text-sm"
            />
          </div>
          <div>
            <Label className="text-stone-700 mb-2 block">
              {t("الشخصية (إنجليزي)", "Persona (English)")}
            </Label>
            <Textarea
              data-testid="persona-en"
              value={settings.persona_en || ""}
              onChange={(e) => setSettings({ ...settings, persona_en: e.target.value })}
              rows={6}
              dir="ltr"
              className="text-sm"
            />
          </div>
          <div className="grid sm:grid-cols-2 gap-4">
            <div>
              <Label className="text-stone-700 mb-2 block">
                {t("رسالة التحويل لموظف (ع)", "Handoff message (AR)")}
              </Label>
              <Input
                data-testid="handoff-ar"
                value={settings.handoff_message_ar || ""}
                onChange={(e) => setSettings({ ...settings, handoff_message_ar: e.target.value })}
                dir="rtl"
              />
            </div>
            <div>
              <Label className="text-stone-700 mb-2 block">
                {t("Handoff message (EN)", "Handoff message (EN)")}
              </Label>
              <Input
                data-testid="handoff-en"
                value={settings.handoff_message_en || ""}
                onChange={(e) => setSettings({ ...settings, handoff_message_en: e.target.value })}
                dir="ltr"
              />
            </div>
            <div>
              <Label className="text-stone-700 mb-2 block">
                {t("رسالة عدم المعرفة (ع)", "Fallback message (AR)")}
              </Label>
              <Input
                data-testid="fallback-ar"
                value={settings.fallback_message_ar || ""}
                onChange={(e) => setSettings({ ...settings, fallback_message_ar: e.target.value })}
                dir="rtl"
              />
            </div>
            <div>
              <Label className="text-stone-700 mb-2 block">
                {t("Fallback message (EN)", "Fallback message (EN)")}
              </Label>
              <Input
                data-testid="fallback-en"
                value={settings.fallback_message_en || ""}
                onChange={(e) => setSettings({ ...settings, fallback_message_en: e.target.value })}
                dir="ltr"
              />
            </div>
          </div>
          <div className="pt-2">
            <Button
              data-testid="save-ai-settings"
              onClick={saveSettings}
              disabled={saving}
              className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl"
            >
              {saving ? <Loader2 className="animate-spin me-2" size={16} /> : <Save className="me-2" size={16} />}
              {t("حفظ الإعدادات", "Save settings")}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Auto-Handoff */}
      <Card data-testid="auto-handoff-card">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <UserCheck size={18} className="text-emerald-700" />
            {t("التحويل التلقائي للموظف", "Auto-handoff")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex items-start justify-between gap-4 rounded-2xl border border-stone-200 bg-stone-50/50 p-4">
            <div className="flex-1">
              <div className="font-semibold text-stone-900 text-sm">
                {t("تفعيل التحويل التلقائي", "Enable auto-handoff")}
              </div>
              <p className="text-xs text-stone-600 mt-1 leading-relaxed">
                {t(
                  "يحوّل المحادثة لموظف بشري تلقائياً (ويوقف البوت لها) عند: عجز البوت عن الإجابة عدة مرات متتالية، أو تكرار العميل نفس السؤال، أو طلب التحدّث مع موظف. يصل تنبيه 🚨 للفريق داخل Chatwoot.",
                  "Auto-routes to a human (and silences the bot) when: the bot can't answer N times in a row, the customer repeats the same question, or asks for a human. The team gets a 🚨 alert inside Chatwoot."
                )}
              </p>
            </div>
            <Switch
              data-testid="auto-handoff-toggle"
              checked={!!settings.auto_handoff_enabled}
              onCheckedChange={(v) => setSettings({ ...settings, auto_handoff_enabled: v })}
            />
          </div>

          <div className={`grid sm:grid-cols-3 gap-4 ${settings.auto_handoff_enabled ? "" : "opacity-50 pointer-events-none"}`}>
            <div>
              <Label className="text-stone-700 mb-2 block text-sm">
                {t("ردود fallback متتالية قبل التحويل", "Consecutive fallbacks before handoff")}
              </Label>
              <Input
                data-testid="auto-handoff-fallback-threshold"
                type="number"
                min={1}
                max={10}
                value={settings.auto_handoff_fallback_threshold ?? 2}
                onChange={(e) => setSettings({
                  ...settings,
                  auto_handoff_fallback_threshold: parseInt(e.target.value || "2", 10),
                })}
              />
              <p className="text-[11px] text-stone-500 mt-1">
                {t("مثال: 2 = يحوّل بعد ردّين \"لا أعرف\"", "e.g. 2 = handoff after two \"I don't know\" replies")}
              </p>
            </div>
            <div>
              <Label className="text-stone-700 mb-2 block text-sm">
                {t("تكرار نفس السؤال قبل التحويل", "Repeat threshold")}
              </Label>
              <Input
                data-testid="auto-handoff-repeat-threshold"
                type="number"
                min={2}
                max={10}
                value={settings.auto_handoff_repeat_threshold ?? 3}
                onChange={(e) => setSettings({
                  ...settings,
                  auto_handoff_repeat_threshold: parseInt(e.target.value || "3", 10),
                })}
              />
              <p className="text-[11px] text-stone-500 mt-1">
                {t("مثال: 3 = يحوّل عند تكرار نفس الرسالة 3 مرات", "e.g. 3 = handoff when same message repeats 3×")}
              </p>
            </div>
            <div>
              <Label className="text-stone-700 mb-2 block text-sm">
                {t("نافذة التكرار (ثوانٍ)", "Repeat window (seconds)")}
              </Label>
              <Input
                data-testid="auto-handoff-repeat-window"
                type="number"
                min={30}
                max={3600}
                step={30}
                value={settings.auto_handoff_repeat_window_seconds ?? 120}
                onChange={(e) => setSettings({
                  ...settings,
                  auto_handoff_repeat_window_seconds: parseInt(e.target.value || "120", 10),
                })}
              />
              <p className="text-[11px] text-stone-500 mt-1">
                {t("المدة التي تُحتسب فيها التكرارات", "Window in which repeats are counted")}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Diagnostics + Test panel */}
      <Card data-testid="ai-diagnostics-card">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Stethoscope size={18} className="text-emerald-700" />
            {t("التشخيص والاختبار", "Diagnostics & Test")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              data-testid="run-diagnostics-btn"
              onClick={runDiagnostics}
              disabled={diagLoading}
              variant="outline"
              className="rounded-xl"
            >
              {diagLoading ? <Loader2 className="animate-spin me-2" size={16} /> : <Stethoscope className="me-2" size={16} />}
              {t("فحص حالة النظام", "Check system status")}
            </Button>
            {diag && (
              <div className="flex flex-wrap gap-2 text-xs" data-testid="diag-badges">
                <StatusBadge
                  ok={diag.provider_ready}
                  label={t(`المزوّد جاهز (${diag.provider})`, `Provider ready (${diag.provider})`)}
                />
                {diag.provider === "emergent" ? (
                  <>
                    <StatusBadge ok={diag.llm_available} label={t("مكتبة AI", "LLM lib")} />
                    <StatusBadge ok={diag.emergent_llm_key_present} label={t("مفتاح Emergent", "Emergent key")} />
                  </>
                ) : (
                  <>
                    <StatusBadge ok={diag.openai_sdk_available} label={t("OpenAI SDK", "OpenAI SDK")} />
                    <StatusBadge ok={diag.openai_api_key_stored} label={t("مفتاح OpenAI", "OpenAI key")} />
                  </>
                )}
                <StatusBadge ok={!!diag.settings?.enabled} label={t("البوت مُفعّل", "Bot enabled")} />
                <StatusBadge ok={diag.knowledge_entries > 0} label={t(`معرفة: ${diag.knowledge_entries}`, `KB: ${diag.knowledge_entries}`)} />
                <StatusBadge ok={diag.whatsapp_routes > 0} label={t(`مسارات: ${diag.whatsapp_routes}`, `Routes: ${diag.whatsapp_routes}`)} />
              </div>
            )}
          </div>

          {diag && (
            <p className="text-xs text-stone-500" data-testid="diag-key-preview">
              {t("المزوّد:", "Provider:")} <code className="bg-stone-100 px-1.5 py-0.5 rounded">{diag.provider}</code>
              {" · "}
              {diag.provider === "emergent" ? (
                <>
                  {t("المفتاح:", "Key:")}{" "}
                  <code className="bg-stone-100 px-1.5 py-0.5 rounded">
                    {diag.emergent_llm_key_preview || t("غير موجود", "missing")}
                  </code>
                </>
              ) : (
                <>
                  {t("المفتاح:", "Key:")}{" "}
                  <code className="bg-stone-100 px-1.5 py-0.5 rounded">
                    {diag.openai_api_key_preview || t("غير محفوظ", "not stored")}
                  </code>
                </>
              )}
              {" · "}
              {t("الموديل:", "Model:")}{" "}
              <code className="bg-stone-100 px-1.5 py-0.5 rounded">{diag.settings?.model || "gpt-4o"}</code>
            </p>
          )}

          <div className="border-t border-stone-200 pt-4 space-y-3">
            <Label className="text-stone-700">
              {t("جرّب البوت برسالة (بدون إرسال واتساب فعلي)", "Try the bot (no real WhatsApp sent)")}
            </Label>
            <div className="flex gap-2">
              <Input
                data-testid="ai-test-input"
                value={testInput}
                onChange={(e) => setTestInput(e.target.value)}
                placeholder={t("اكتب رسالة العميل هنا...", "Type a customer message...")}
                dir="auto"
              />
              <Button
                data-testid="ai-test-send-btn"
                onClick={runTestReply}
                disabled={testing || !testInput.trim()}
                className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl"
              >
                {testing ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}
              </Button>
            </div>

            {testResult && (
              <div
                data-testid="ai-test-result"
                className={`rounded-xl p-4 text-sm space-y-2 border ${
                  testResult.reply
                    ? "bg-emerald-50 border-emerald-200"
                    : "bg-amber-50 border-amber-200"
                }`}
              >
                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-stone-600">
                  <span>{t("النتيجة", "Result")}:</span>
                  <code className="bg-white border border-stone-200 px-2 py-0.5 rounded">{testResult.action}</code>
                  {testResult.lang && <Badge variant="outline" className="text-[10px]">{testResult.lang.toUpperCase()}</Badge>}
                </div>
                {testResult.reply ? (
                  <p className="text-stone-800 whitespace-pre-wrap" dir="auto">{testResult.reply}</p>
                ) : (
                  <p className="text-amber-800">
                    {testResult.error
                      ? `${t("خطأ:", "Error:")} ${testResult.error}`
                      : t(
                          "لم يُولّد البوت أي رد. تحقّق من تفعيل البوت ومفتاح Emergent وقاعدة المعرفة.",
                          "Bot did not generate a reply. Verify bot is enabled, Emergent key is set, and knowledge base has entries."
                        )}
                  </p>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Knowledge base */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BookOpen size={18} className="text-emerald-700" />
            {t("قاعدة المعرفة", "Knowledge base")}
            <Badge className="bg-stone-100 text-stone-700 hover:bg-stone-100 border-0">
              {knowledge.length}
            </Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          {/* Add new */}
          <div className="rounded-2xl border border-stone-200 bg-stone-50/50 p-4 space-y-3">
            <Input
              data-testid="new-knowledge-title"
              placeholder={t("العنوان (مثل: الأسعار)", "Title (e.g. Pricing)")}
              value={newItem.title}
              onChange={(e) => setNewItem({ ...newItem, title: e.target.value })}
            />
            <Textarea
              data-testid="new-knowledge-content"
              placeholder={t(
                "أدخل المعلومات هنا (الأسعار، الميزات، الأسئلة الشائعة...)",
                "Enter knowledge content (prices, features, FAQs...)"
              )}
              value={newItem.content}
              onChange={(e) => setNewItem({ ...newItem, content: e.target.value })}
              rows={4}
            />
            <div className="flex items-center justify-between gap-3">
              <select
                data-testid="new-knowledge-lang"
                value={newItem.lang}
                onChange={(e) => setNewItem({ ...newItem, lang: e.target.value })}
                className="border border-stone-300 rounded-lg px-3 py-2 text-sm bg-white"
              >
                <option value="both">{t("عربي وإنجليزي", "Both languages")}</option>
                <option value="ar">{t("عربي فقط", "Arabic only")}</option>
                <option value="en">{t("إنجليزي فقط", "English only")}</option>
              </select>
              <Button
                data-testid="add-knowledge-btn"
                onClick={addKnowledge}
                disabled={adding || !newItem.title.trim() || !newItem.content.trim()}
                className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl"
              >
                {adding ? <Loader2 className="animate-spin me-2" size={16} /> : <Plus className="me-2" size={16} />}
                {t("إضافة", "Add")}
              </Button>
            </div>
          </div>

          {/* List */}
          {knowledge.length === 0 ? (
            <div className="text-center py-10 text-stone-400 text-sm" data-testid="knowledge-empty">
              {t("لا توجد معلومات بعد. أضف أول معلومة لتفعيل البوت.", "No knowledge yet. Add your first entry to enable the bot.")}
            </div>
          ) : (
            <div className="space-y-3" data-testid="knowledge-list">
              {knowledge.map((k) => (
                <div
                  key={k.id}
                  data-testid={`knowledge-item-${k.id}`}
                  className="rounded-xl border border-stone-200 bg-white p-4 flex items-start justify-between gap-4"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="font-semibold text-stone-900">{k.title}</span>
                      <Badge variant="outline" className="text-[10px]">
                        {k.lang === "ar" ? "AR" : k.lang === "en" ? "EN" : "AR + EN"}
                      </Badge>
                    </div>
                    <p className="text-sm text-stone-600 whitespace-pre-wrap break-words">
                      {k.content}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    data-testid={`delete-knowledge-${k.id}`}
                    onClick={() => deleteKnowledge(k.id)}
                    className="text-red-600 hover:text-red-700 hover:bg-red-50"
                  >
                    <Trash2 size={16} />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatusBadge({ ok, label }) {
  return (
    <span
      data-testid={`status-${ok ? "ok" : "fail"}`}
      className={`inline-flex items-center gap-1 px-2 py-1 rounded-full border text-[11px] font-medium ${
        ok
          ? "bg-emerald-50 border-emerald-200 text-emerald-800"
          : "bg-red-50 border-red-200 text-red-800"
      }`}
    >
      {ok ? <CheckCircle2 size={12} /> : <XCircle size={12} />}
      {label}
    </span>
  );
}
