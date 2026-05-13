import React from "react";
import { MessagesSquare } from "lucide-react";
import { useLang } from "@/contexts/LanguageContext";

export const Logo = ({ size = "default" }) => {
  const { lang } = useLang();
  const sizes = {
    small: { icon: 28, text: "text-lg" },
    default: { icon: 36, text: "text-xl" },
    large: { icon: 48, text: "text-2xl" },
  };
  const s = sizes[size];

  return (
    <div className="flex items-center gap-2.5" data-testid="brand-logo">
      <div className="relative">
        <div className="absolute inset-0 bg-emerald-700 rounded-xl blur-md opacity-30"></div>
        <div className="relative bg-gradient-to-br from-emerald-700 to-emerald-900 rounded-xl p-1.5 flex items-center justify-center">
          <MessagesSquare size={s.icon - 12} className="text-amber-400" strokeWidth={2.5} />
        </div>
      </div>
      <span className={`font-heading font-bold tracking-tight ${s.text} text-stone-900`}>
        {lang === "ar" ? "سوشال هَب" : "SocialHub"}
      </span>
    </div>
  );
};
