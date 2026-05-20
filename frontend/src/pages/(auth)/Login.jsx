import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { useAuth, formatApiErrorDetail } from "@/contexts/AuthContext";
import { useLang } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, ArrowLeft, ArrowRight, Loader2, AlertCircle } from "lucide-react";

const schema = z.object({
  email: z.string().min(1, "البريد الإلكتروني مطلوب").email("صيغة البريد غير صحيحة"),
  password: z.string().min(1, "كلمة المرور مطلوبة"),
});

export default function Login() {
  const { lang } = useLang();
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm({ resolver: zodResolver(schema), defaultValues: { email: "", password: "" } });

  const onSubmit = async (values) => {
    setServerError("");
    setSubmitting(true);
    try {
      const user = await login(values.email, values.password);
      const intended = location.state?.from;
      const target = intended && intended !== "/login" ? intended : user.role === "ADMIN" ? "/admin" : "/dashboard";
      navigate(target, { replace: true });
    } catch (e) {
      setServerError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
      setSubmitting(false);
    }
  };

  return (
    <div className="w-full max-w-md" data-testid="login-page">
      <div className="bg-white border border-stone-200 rounded-3xl p-8 md:p-10 shadow-sm">
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900 mb-2 text-center">
          {lang === "ar" ? "أهلاً بعودتك" : "Welcome back"}
        </h1>
        <p className="text-stone-600 text-center mb-8">
          {lang === "ar" ? "سجّل دخولك للمتابعة إلى لوحة التحكم" : "Sign in to continue to your dashboard"}
        </p>

        {serverError && (
          <div
            data-testid="login-error"
            className="mb-5 flex items-start gap-2 p-3.5 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800"
          >
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="email" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "البريد الإلكتروني" : "Email"}
            </Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              data-testid="login-email"
              placeholder={lang === "ar" ? "you@company.com" : "you@company.com"}
              className="h-12 rounded-xl"
              {...register("email")}
            />
            {errors.email && (
              <p className="text-xs text-red-600 mt-1.5" data-testid="login-email-error">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <Label htmlFor="password" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "كلمة المرور" : "Password"}
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPw ? "text" : "password"}
                autoComplete="current-password"
                data-testid="login-password"
                placeholder="••••••••"
                className="h-12 rounded-xl pe-11"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                data-testid="toggle-password"
                className="absolute top-1/2 -translate-y-1/2 end-3 p-1 text-stone-400 hover:text-stone-700"
                aria-label="toggle password visibility"
              >
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {errors.password && (
              <p className="text-xs text-red-600 mt-1.5" data-testid="login-password-error">
                {errors.password.message}
              </p>
            )}
          </div>

          <Button
            type="submit"
            data-testid="login-submit"
            disabled={submitting}
            className="w-full h-12 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-semibold mt-2 disabled:opacity-60"
          >
            {submitting ? (
              <>
                <Loader2 className="animate-spin me-2" size={16} />
                {lang === "ar" ? "جاري الدخول..." : "Signing in..."}
              </>
            ) : (
              <>
                {lang === "ar" ? "تسجيل الدخول" : "Sign in"}
                <Arrow className="ms-2" size={16} />
              </>
            )}
          </Button>

          <p className="text-sm text-center -mt-2">
            <Link
              to="/auth/forgot-password"
              data-testid="link-forgot-password"
              className="text-stone-600 hover:text-emerald-800 hover:underline"
            >
              {lang === "ar" ? "نسيت كلمة المرور؟" : "Forgot password?"}
            </Link>
          </p>
        </form>

        <p className="text-sm text-stone-600 text-center mt-8">
          {lang === "ar" ? "ليس لديك حساب؟" : "Don't have an account?"}{" "}
          <Link to="/register" data-testid="link-register" className="text-emerald-800 font-semibold hover:text-emerald-900 hover:underline">
            {lang === "ar" ? "إنشاء حساب" : "Create account"}
          </Link>
        </p>
      </div>
    </div>
  );
}
