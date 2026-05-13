import React from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { useLang } from "@/contexts/LanguageContext";
import { ArrowLeft, ArrowRight, Construction } from "lucide-react";

export default function ComingSoon({ title, description, testId }) {
  const { lang } = useLang();
  const Arrow = lang === "ar" ? ArrowLeft : ArrowRight;
  return (
    <div className="min-h-screen flex items-center justify-center px-6 py-20 bg-[#FDFBF7]" data-testid={testId || "coming-soon"}>
      <div className="max-w-md w-full text-center">
        <div className="flex justify-center mb-6">
          <Link to="/"><Logo size="large" /></Link>
        </div>
        <div className="bg-white border border-stone-200 rounded-3xl p-10 shadow-sm">
          <div className="w-16 h-16 mx-auto rounded-2xl bg-amber-100 flex items-center justify-center mb-5">
            <Construction size={28} className="text-amber-700" />
          </div>
          <h1 className="font-heading text-2xl md:text-3xl font-bold text-stone-900 mb-3">{title}</h1>
          <p className="text-stone-600 leading-relaxed mb-7">{description}</p>
          <Link to="/">
            <Button className="bg-emerald-800 hover:bg-emerald-900 text-white rounded-xl h-12 px-6">
              {lang === "ar" ? "العودة للصفحة الرئيسية" : "Back to home"}
              <Arrow className="ms-2" size={16} />
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
