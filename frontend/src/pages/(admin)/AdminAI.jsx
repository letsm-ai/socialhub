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
import { Bot, Plus, Trash2, Loader2, BookOpen, Sparkles, AlertCircle, Save } from "lucide-react";

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
      const { data } = await api.put("/admin/ai/settings", settings);
      setSettings(data);
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
