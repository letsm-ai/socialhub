import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { useLang } from "@/contexts/LanguageContext";

export const FAQ = () => {
  const { t } = useLang();
  const items = t("faq.items");

  return (
    <section id="faq" className="py-24 md:py-32" data-testid="faq-section">
      <div className="max-w-3xl mx-auto px-6">
        <div className="mb-12 text-center">
          <p className="text-xs font-bold uppercase tracking-[0.15em] text-emerald-700 mb-3">
            {t("faq.overline")}
          </p>
          <h2 className="font-heading text-3xl md:text-5xl font-bold text-stone-900 leading-tight">
            {t("faq.title")}
          </h2>
        </div>

        <Accordion type="single" collapsible className="space-y-3">
          {Array.isArray(items) &&
            items.map((it, i) => (
              <AccordionItem
                key={i}
                value={`item-${i}`}
                data-testid={`faq-item-${i}`}
                className="bg-white border border-stone-200 rounded-2xl px-6 hover:border-emerald-300 transition-colors data-[state=open]:border-emerald-700 data-[state=open]:shadow-md"
              >
                <AccordionTrigger className="text-start font-heading font-semibold text-stone-900 hover:no-underline py-5 text-base md:text-lg">
                  {it.q}
                </AccordionTrigger>
                <AccordionContent className="text-stone-600 leading-relaxed pb-5 text-base">
                  {it.a}
                </AccordionContent>
              </AccordionItem>
            ))}
        </Accordion>
      </div>
    </section>
  );
};
