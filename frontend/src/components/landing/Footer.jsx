import React from "react";
import { Logo } from "@/components/Logo";
import { useLang } from "@/contexts/LanguageContext";
import { MapPin, Mail, Twitter, Linkedin, Instagram } from "lucide-react";

export const Footer = () => {
  const { t } = useLang();

  const cols = [
    {
      title: t("footer.product"),
      links: [
        { l: t("footer.links.features"), h: "#features" },
        { l: t("footer.links.pricing"), h: "#pricing" },
        { l: t("footer.links.integrations"), h: "#" },
      ],
    },
    {
      title: t("footer.company"),
      links: [
        { l: t("footer.links.about"), h: "#" },
        { l: t("footer.links.blog"), h: "#" },
        { l: t("footer.links.careers"), h: "#" },
      ],
    },
    {
      title: t("footer.legal"),
      links: [
        { l: t("footer.links.privacy"), h: "#" },
        { l: t("footer.links.terms"), h: "#" },
        { l: t("footer.links.cookies"), h: "#" },
      ],
    },
  ];

  return (
    <footer className="bg-stone-900 text-stone-300 pt-20 pb-10" data-testid="main-footer">
      <div className="max-w-7xl mx-auto px-6 lg:px-12">
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10 mb-14">
          <div className="col-span-2">
            <div className="mb-4 [&_span]:!text-white">
              <Logo />
            </div>
            <p className="text-sm text-stone-400 max-w-xs leading-relaxed mb-5">
              {t("footer.tagline")}
            </p>
            <div className="flex items-center gap-2 text-sm text-stone-400 mb-2">
              <MapPin size={14} />
              <span>{t("footer.address")}</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-stone-400 mb-5">
              <Mail size={14} />
              <a href="mailto:hello@socialhub.om" className="hover:text-amber-400">hello@socialhub.om</a>
            </div>
            <div className="flex gap-2">
              {[
                { icon: Twitter, label: "twitter" },
                { icon: Linkedin, label: "linkedin" },
                { icon: Instagram, label: "instagram" },
              ].map((s, i) => (
                <a
                  key={i}
                  href="#"
                  data-testid={`social-${s.label}`}
                  className="w-9 h-9 rounded-xl bg-stone-800 hover:bg-emerald-700 transition-colors flex items-center justify-center"
                >
                  <s.icon size={16} />
                </a>
              ))}
            </div>
          </div>

          {cols.map((col, i) => (
            <div key={i}>
              <h4 className="font-heading font-bold text-white mb-4 text-sm">{col.title}</h4>
              <ul className="space-y-3">
                {col.links.map((l, k) => (
                  <li key={k}>
                    <a
                      href={l.h}
                      className="text-sm text-stone-400 hover:text-amber-400 transition-colors"
                    >
                      {l.l}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="pt-8 border-t border-stone-800 flex flex-col md:flex-row items-center justify-between gap-4">
          <p className="text-xs text-stone-500">
            © {new Date().getFullYear()} SocialHub — {t("footer.rights")}
          </p>
          <p className="text-xs text-stone-500">
            🇴🇲 Made with care in Oman
          </p>
        </div>
      </div>
    </footer>
  );
};
