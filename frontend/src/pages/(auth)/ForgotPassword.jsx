import React, { useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { useLang } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ArrowLeft, ArrowRight, Loader2, Mail, CheckCircle2 } from "lucide-react";

const API = process.env.REACT_APP_BACKEND_URL;

export default function ForgotPassword() {
  const { lang } = useLang();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    try {
      await axios.post(`${API}/api/auth/forgot-password`, { email, lang });
      setDone(true);
    } catch (err) {
      // Backend never reveals if the email exists, so we still show success
      setDone(true);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-stone-50">
      <div className="w-full max-w-md bg-white rounded-3xl shadow-sm border border-stone-200 p-8 sm:p-10">
        <h1 className="text-2xl font-bold text-stone-900 mb-2">
          {lang === "ar" ? "نسيت كلمة المرور؟" : "Forgot password?"}
        </h1>
        <p className="text-sm text-stone-600 mb-8">
          {lang === "ar"
            ? "أدخل بريدك المسجّل وسنرسل رابط إعادة التعيين."
            : "Enter the email on your account and we'll send a reset link."}
        </p>

        {done ? (
          <div
            data-testid="forgot-success"
            className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5 flex items-start gap-3"
          >
            <CheckCircle2 className="text-emerald-700 shrink-0 mt-0.5" size={22} />
            <div>
              <p className="text-emerald-900 font-semibold mb-1">
                {lang === "ar" ? "تم الإرسال" : "Check your inbox"}
              </p>
              <p className="text-sm text-emerald-800">
                {lang === "ar"
                  ? "إذا كان البريد مسجّلاً، ستجد رابط إعادة التعيين خلال دقيقة. الرابط صالح لمدة ٣٠ دقيقة."
                  : "If the email is registered, you'll see the reset link within a minute. The link is valid for 30 minutes."}
              </p>
              <Link
                to="/login"
                data-testid="back-to-login"
                className="inline-block mt-4 text-emerald-800 font-semibold hover:underline text-sm"
              >
                {lang === "ar" ? "← العودة لتسجيل الدخول" : "Back to sign in →"}
              </Link>
            </div>
          </div>
        ) : (
          <form onSubmit={onSubmit} className="space-y-5" data-testid="forgot-form">
            <div>
              <Label htmlFor="email" className="text-stone-700 mb-2 block">
                {lang === "ar" ? "البريد الإلكتروني" : "Email"}
              </Label>
              <div className="relative">
                <Mail size={16} className="absolute top-1/2 -translate-y-1/2 start-3 text-stone-400" />
                <Input
                  id="email"
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  data-testid="forgot-email"
                  className="h-12 ps-9 rounded-xl border-stone-300"
                />
              </div>
            </div>
            <Button
              type="submit"
              data-testid="forgot-submit"
              disabled={submitting}
              className="w-full h-12 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-semibold disabled:opacity-60"
            >
              {submitting ? (
                <>
                  <Loader2 className="animate-spin me-2" size={16} />
                  {lang === "ar" ? "جاري الإرسال..." : "Sending..."}
                </>
              ) : (
                <>
                  {lang === "ar" ? "إرسال رابط الاستعادة" : "Send reset link"}
                  <Arrow className="ms-2" size={16} />
                </>
              )}
            </Button>
            <p className="text-sm text-center text-stone-600">
              <Link to="/login" data-testid="forgot-cancel" className="hover:underline">
                {lang === "ar" ? "العودة لتسجيل الدخول" : "Back to sign in"}
              </Link>
            </p>
          </form>
        )}
      </div>
    </div>
  );
}
