import React from "react";
import { Outlet } from "react-router-dom";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

/**
 * MarketingLayout - shared layout for public marketing pages.
 * Wraps children with the global Navbar + Footer.
 * Used by /  (marketing route group).
 */
export default function MarketingLayout() {
  return (
    <div className="min-h-screen bg-[#FDFBF7]" data-testid="marketing-layout">
      <Navbar />
      <main>
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
