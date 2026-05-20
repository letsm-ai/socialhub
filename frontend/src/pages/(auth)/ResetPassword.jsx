import React, { useState, useEffect } from "react";
import { Link, useSearchParams, useNavigate } from "react-router-dom";
import axios from "axios";
import { useLang } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, Loader2, CheckCircle2, AlertCircle, Lock } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ResetPassword() {
  const { lang } = useLang();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get("token") || "";

  const [pw, setPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) setError(lang === "ar" ? "رابط غير صالح" : "Invalid reset link");
  }, [token, lang]);

  const onSubmit = async (e) => {
    e.preventDefault();
    setError("");
    if (pw.length < 8) {
      setError(
        lang === "ar"
          ? "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
          : "Password must be at least 8 characters"
      );
      return;
    }
    if (pw !== confirmPw) {
      setError(lang === "ar" ? "كلمة المرور غير متطابقة" : "Passwords do not match");
      return;
    }
    setSubmitting(true);
    try {
      await axios.post(`${API}/api/auth/reset-password`, {
        token,
        new_password: pw,
      });
      setSuccess(true);
      setTimeout(() => navigate("/login"), 2500);
    } catch (err) {
      const detail = err?.response?.data?.detail || "Something went wrong";
      const messages = {
        invalid_or_used_token: lang === "ar" ? "الرابط منتهي أو تم استخدامه" : "Link is invalid or already used",
        expired_token: lang === "ar" ? "انتهت صلاحية الرابط، اطلب رابطاً جديداً" : "Link expired, request a new one",
        user_not_found: lang === "ar" ? "المستخدم غير موجود" : "User not found",
      };
      setError(messages[detail] || detail);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-stone-50">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-sm border border-stone-200 p-8 sm:p-10">
        <h1 className="text-2xl font-bold text-stone-900 mb-2">
          {lang === "ar" ? "إعادة تعيين كلمة المرور" : "Reset password"}
        </h1>

        {success ? (
          <div
            data-testid="reset-success"
            className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 flex items-start gap-3"
          >
            <CheckCircle2 className="text-emerald-700 shrink-0 mt-0.5" size={22} />
            <div>
              <p className="text-emerald-900 font-semibold mb-1">
                {lang === "ar" ? "تم تعيين كلمة المرور بنجاح" : "Password updated"}
              </p>
              <p className="text-sm text-emerald-800">
                {lang === "ar"
                  ? "سيتم تحويلك لصفحة تسجيل الدخول خلال ثوانٍ..."
                  : "Redirecting you to sign in..."}
              </p>
            </div>
          </div>
        ) : (
          <>
            <p className="text-sm text-stone-600 mb-8">
              {lang === "ar"
                ? "اختر كلمة مرور قوية لحسابك."
                : "Choose a strong password for your account."}
            </p>
            <form onSubmit={onSubmit} className="space-y-5" data-testid="reset-form">
              <div>
                <Label htmlFor="pw" className="text-stone-700 mb-2 block">
                  {lang === "ar" ? "كلمة المرور الجديدة" : "New password"}
                </Label>
                <div className="relative">
                  <Lock size={16} className="absolute top-1/2 -translate-y-1/2 start-3 text-stone-400" />
                  <Input
                    id="pw"
                    type={showPw ? "text" : "password"}
                    required
                    value={pw}
                    onChange={(e) => setPw(e.target.value)}
                    data-testid="reset-password"
                    placeholder="••••••••"
                    className="h-12 ps-9 pe-10 rounded-xl border-stone-300"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute top-1/2 -translate-y-1/2 end-3 p-1 text-stone-400 hover:text-stone-700"
                    aria-label="toggle"
                  >
                    {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>
              <div>
                <Label htmlFor="confirm" className="text-stone-700 mb-2 block">
                  {lang === "ar" ? "تأكيد كلمة المرور" : "Confirm password"}
                </Label>
                <Input
                  id="confirm"
                  type={showPw ? "text" : "password"}
                  required
                  value={confirmPw}
                  onChange={(e) => setConfirmPw(e.target.value)}
                  data-testid="reset-confirm-password"
                  placeholder="••••••••"
                  className="h-12 rounded-xl border-stone-300"
                />
              </div>

              {error && (
                <div
                  data-testid="reset-error"
                  className="rounded-xl bg-red-50 border border-red-200 text-red-700 text-sm p-3 flex items-start gap-2"
                >
                  <AlertCircle size={16} className="shrink-0 mt-0.5" />
                  <span>{error}</span>
                </div>
              )}

              <Button
                type="submit"
                data-testid="reset-submit"
                disabled={submitting || !token}
                className="w-full h-12 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-semibold disabled:opacity-60"
              >
                {submitting ? (
                  <>
                    <Loader2 className="animate-spin me-2" size={16} />
                    {lang === "ar" ? "جاري الحفظ..." : "Saving..."}
                  </>
                ) : (
                  lang === "ar" ? "تعيين كلمة المرور" : "Set new password"
                )}
              </Button>

              <p className="text-sm text-center text-stone-600">
                <Link to="/login" className="hover:underline">
                  {lang === "ar" ? "العودة لتسجيل الدخول" : "Back to sign in"}
                </Link>
              </p>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
