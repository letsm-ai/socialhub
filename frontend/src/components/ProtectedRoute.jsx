import React from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";

/**
 * ProtectedRoute - wraps authenticated routes.
 *
 * Props:
 *   - requireRole: optional 'ADMIN' or 'CLIENT'. If set, only users with that role pass.
 *   - children:    the route content (or use <Outlet /> in nested layouts).
 */
export default function ProtectedRoute({ children, requireRole }) {
  const { user } = useAuth();
  const location = useLocation();

  // Still checking session
  if (user === null) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FDFBF7]" data-testid="auth-loading">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-emerald-200 border-t-emerald-700 rounded-full animate-spin"></div>
          <p className="text-sm text-stone-500">جاري التحقق...</p>
        </div>
      </div>
    );
  }

  // Not authenticated
  if (user === false) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  // Role mismatch
  if (requireRole && user.role !== requireRole) {
    const fallback = user.role === "ADMIN" ? "/admin" : "/dashboard";
    return <Navigate to={fallback} replace />;
  }

  return children;
}
