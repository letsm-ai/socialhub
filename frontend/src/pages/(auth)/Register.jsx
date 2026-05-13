import React, { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Link, useNavigate } from "react-router-dom";
import { useAuth, formatApiErrorDetail } from "@/contexts/AuthContext";
import { useLang } from "@/contexts/LanguageContext";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Eye, EyeOff, ArrowLeft, ArrowRight, Loader2, AlertCircle, Check } from "lucide-react";

const schema = z
  .object({
    name: z.string().min(2, "الاسم قصير جداً").max(80),
    email: z.string().email("صيغة البريد غير صحيحة"),
    company_name: z.string().max(120).optional().or(z.literal("")),
    password: z
      .string()
      .min(8, "كلمة المرور يجب أن تكون ٨ أحرف على الأقل")
      .regex(/[a-zA-Z]/, "يجب أن تحتوي على حرف")
      .regex(/[0-9]/, "يجب أن تحتوي على رقم"),
    confirm_password: z.string(),
  })
  .refine((d) => d.password === d.confirm_password, {
    message: "كلمتا المرور غير متطابقتين",
    path: ["confirm_password"],
  });

export default function Register() {
  const { lang } = useLang();
  const { register: doRegister } = useAuth();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState("");
  const [showPw, setShowPw] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { name: "", email: "", company_name: "", password: "", confirm_password: "" },
  });
  const pw = watch("password", "");

  const onSubmit = async (values) => {
    setServerError("");
    setSubmitting(true);
    try {
      const user = await doRegister({
        name: values.name,
        email: values.email,
        password: values.password,
        company_name: values.company_name || undefined,
      });
      navigate(user.role === "ADMIN" ? "/admin" : "/dashboard", { replace: true });
    } catch (e) {
      setServerError(formatApiErrorDetail(e.response?.data?.detail) || e.message);
      setSubmitting(false);
    }
  };

  const pwChecks = [
    { ok: pw.length >= 8, label: lang === "ar" ? "٨ أحرف على الأقل" : "At least 8 characters" },
    { ok: /[a-zA-Z]/.test(pw), label: lang === "ar" ? "حرف" : "A letter" },
    { ok: /[0-9]/.test(pw), label: lang === "ar" ? "رقم" : "A number" },
  ];

  return (
    <div className="w-full max-w-md" data-testid="register-page">
      <div className="bg-white border border-stone-200 rounded-3xl p-8 md:p-10 shadow-sm">
        <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900 mb-2 text-center">
          {lang === "ar" ? "أنشئ حسابك" : "Create your account"}
        </h1>
        <p className="text-stone-600 text-center mb-8">
          {lang === "ar" ? "تجربة مجانية ١٤ يوم، بدون بطاقة ائتمان" : "14-day free trial, no credit card"}
        </p>

        {serverError && (
          <div
            data-testid="register-error"
            className="mb-5 flex items-start gap-2 p-3.5 bg-red-50 border border-red-200 rounded-xl text-sm text-red-800"
          >
            <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
            <span>{serverError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <Label htmlFor="name" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "الاسم الكامل" : "Full name"}
            </Label>
            <Input id="name" data-testid="reg-name" className="h-12 rounded-xl" {...register("name")} />
            {errors.name && <p className="text-xs text-red-600 mt-1.5">{errors.name.message}</p>}
          </div>

          <div>
            <Label htmlFor="email" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "البريد الإلكتروني" : "Email"}
            </Label>
            <Input id="email" type="email" autoComplete="email" data-testid="reg-email" className="h-12 rounded-xl" {...register("email")} />
            {errors.email && <p className="text-xs text-red-600 mt-1.5">{errors.email.message}</p>}
          </div>

          <div>
            <Label htmlFor="company_name" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "اسم الشركة (اختياري)" : "Company name (optional)"}
            </Label>
            <Input id="company_name" data-testid="reg-company" className="h-12 rounded-xl" {...register("company_name")} />
          </div>

          <div>
            <Label htmlFor="password" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "كلمة المرور" : "Password"}
            </Label>
            <div className="relative">
              <Input
                id="password"
                type={showPw ? "text" : "password"}
                autoComplete="new-password"
                data-testid="reg-password"
                className="h-12 rounded-xl pe-11"
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                className="absolute top-1/2 -translate-y-1/2 end-3 p-1 text-stone-400 hover:text-stone-700"
                aria-label="toggle password visibility"
              >
                {showPw ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
            {pw && (
              <ul className="mt-2 space-y-1" data-testid="pw-checklist">
                {pwChecks.map((c, i) => (
                  <li key={i} className={`flex items-center gap-1.5 text-xs ${c.ok ? "text-emerald-700" : "text-stone-400"}`}>
                    <Check size={12} strokeWidth={3} />
                    <span>{c.label}</span>
                  </li>
                ))}
              </ul>
            )}
            {errors.password && !pw && <p className="text-xs text-red-600 mt-1.5">{errors.password.message}</p>}
          </div>

          <div>
            <Label htmlFor="confirm_password" className="text-sm font-medium text-stone-700 mb-1.5 block">
              {lang === "ar" ? "تأكيد كلمة المرور" : "Confirm password"}
            </Label>
            <Input
              id="confirm_password"
              type={showPw ? "text" : "password"}
              autoComplete="new-password"
              data-testid="reg-confirm"
              className="h-12 rounded-xl"
              {...register("confirm_password")}
            />
            {errors.confirm_password && <p className="text-xs text-red-600 mt-1.5">{errors.confirm_password.message}</p>}
          </div>

          <Button
            type="submit"
            data-testid="register-submit"
            disabled={submitting}
            className="w-full h-12 rounded-xl bg-emerald-800 hover:bg-emerald-900 text-white font-semibold mt-2 disabled:opacity-60"
          >
            {submitting ? (
              <>
                <Loader2 className="animate-spin me-2" size={16} />
                {lang === "ar" ? "جاري الإنشاء..." : "Creating account..."}
              </>
            ) : (
              <>
                {lang === "ar" ? "إنشاء الحساب" : "Create account"}
                <Arrow className="ms-2" size={16} />
              </>
            )}
          </Button>
        </form>

        <p className="text-sm text-stone-600 text-center mt-8">
          {lang === "ar" ? "لديك حساب بالفعل؟" : "Already have an account?"}{" "}
          <Link to="/login" data-testid="link-login" className="text-emerald-800 font-semibold hover:text-emerald-900 hover:underline">
            {lang === "ar" ? "تسجيل الدخول" : "Sign in"}
          </Link>
        </p>
      </div>
    </div>
  );
}
