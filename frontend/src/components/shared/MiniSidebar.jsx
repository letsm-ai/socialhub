import React from "react";
import { Link, useLocation } from "react-router-dom";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { MessagesSquare } from "lucide-react";

/**
 * MiniSidebar — narrow icon-only navigation (respond.io style).
 *
 * Props:
 *   items: [{ to, label, icon: Component, testId, external? }]
 *   theme: "light" | "dark"
 *   bottomItems: optional same shape, anchored at bottom
 */
export default function MiniSidebar({ items, theme = "light", bottomItems = [] }) {
  const loc = useLocation();
  const dark = theme === "dark";

  return (
    <TooltipProvider delayDuration={120}>
      <aside
        data-testid="mini-sidebar"
        className={`hidden md:flex flex-col items-center w-[68px] flex-shrink-0 min-h-[calc(100vh-0px)] py-4 ${
          dark
            ? "bg-stone-950 border-e border-stone-800"
            : "bg-white border-e border-stone-200"
        }`}
      >
        {/* Brand glyph */}
        <Link
          to="/"
          data-testid="mini-sidebar-logo"
          className="mb-6 group"
          aria-label="SocialHub home"
        >
          <div className="relative">
            <div className="absolute inset-0 bg-emerald-700 rounded-xl blur-md opacity-30 group-hover:opacity-50 transition-opacity"></div>
            <div className="relative w-10 h-10 bg-gradient-to-br from-emerald-700 to-emerald-900 rounded-xl flex items-center justify-center">
              <MessagesSquare size={20} className="text-amber-400" strokeWidth={2.5} />
            </div>
          </div>
        </Link>

        <nav className="flex-1 flex flex-col gap-1 w-full px-2">
          {items.map((it) => (
            <SidebarItem key={it.to + it.label} item={it} loc={loc} dark={dark} />
          ))}
        </nav>

        {bottomItems.length > 0 && (
          <div className="mt-auto flex flex-col gap-1 w-full px-2 pt-3 border-t border-stone-200/60">
            {bottomItems.map((it) => (
              <SidebarItem key={"b-" + it.label} item={it} loc={loc} dark={dark} />
            ))}
          </div>
        )}
      </aside>
    </TooltipProvider>
  );
}

const SidebarItem = ({ item, loc, dark }) => {
  const Icon = item.icon;
  const active = item.to && (loc.pathname === item.to || (item.matchPrefix && loc.pathname.startsWith(item.matchPrefix)));

  const base =
    "relative w-12 h-12 mx-auto rounded-xl flex items-center justify-center transition-all duration-150";
  const activeCls = dark
    ? "bg-emerald-600 text-white shadow-lg shadow-emerald-900/40"
    : "bg-emerald-700 text-white shadow-md shadow-emerald-900/20";
  const inactiveCls = dark
    ? "text-stone-400 hover:bg-stone-800 hover:text-emerald-400"
    : "text-stone-500 hover:bg-stone-100 hover:text-emerald-800";

  const content = (
    <>
      <Icon size={20} strokeWidth={active ? 2.5 : 2} />
      {item.badge && (
        <span className="absolute -top-1 -end-1 min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-stone-900 text-[10px] font-bold flex items-center justify-center">
          {item.badge}
        </span>
      )}
      {/* Active indicator strip */}
      {active && (
        <span className="absolute start-[-8px] inset-y-2 w-1 rounded-full bg-amber-400"></span>
      )}
    </>
  );

  const button = item.external ? (
    <a
      href={item.to}
      target="_blank"
      rel="noopener noreferrer"
      data-testid={item.testId}
      onClick={item.onClick}
      className={`${base} ${active ? activeCls : inactiveCls}`}
    >
      {content}
    </a>
  ) : item.onClick ? (
    <button
      type="button"
      data-testid={item.testId}
      onClick={item.onClick}
      className={`${base} ${active ? activeCls : inactiveCls}`}
    >
      {content}
    </button>
  ) : (
    <Link
      to={item.to}
      data-testid={item.testId}
      className={`${base} ${active ? activeCls : inactiveCls}`}
    >
      {content}
    </Link>
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent side="right" className="bg-stone-900 text-white border-stone-800 font-semibold">
        {item.label}
      </TooltipContent>
    </Tooltip>
  );
};
