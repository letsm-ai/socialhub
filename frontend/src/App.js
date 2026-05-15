import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { LanguageProvider } from "@/contexts/LanguageContext";
import { AuthProvider } from "@/contexts/AuthContext";
import ProtectedRoute from "@/components/ProtectedRoute";

// Layouts
import MarketingLayout from "@/layouts/MarketingLayout";
import AuthLayout from "@/layouts/AuthLayout";
import DashboardLayout from "@/layouts/DashboardLayout";
import AdminLayout from "@/layouts/AdminLayout";

// Pages
import LandingPage from "@/pages/(marketing)/LandingPage";
import Login from "@/pages/(auth)/Login";
import Register from "@/pages/(auth)/Register";
import Dashboard from "@/pages/(dashboard)/Dashboard";
import Billing from "@/pages/(dashboard)/Billing";
import Wallet from "@/pages/(dashboard)/Wallet";
import Channels from "@/pages/(dashboard)/Channels";
import AdminDashboard from "@/pages/(admin)/AdminDashboard";
import AdminClients from "@/pages/(admin)/AdminClients";
import AdminBilling from "@/pages/(admin)/AdminBilling";
import AdminQuotas from "@/pages/(admin)/AdminQuotas";

function App() {
  return (
    <LanguageProvider>
      <AuthProvider>
        <div className="App">
          <BrowserRouter>
            <Routes>
              {/* (marketing) — public */}
              <Route element={<MarketingLayout />}>
                <Route path="/" element={<LandingPage />} />
              </Route>

              {/* (auth) — public */}
              <Route element={<AuthLayout />}>
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
              </Route>

              {/* (dashboard) — CLIENT only */}
              <Route
                element={
                  <ProtectedRoute requireRole="CLIENT">
                    <DashboardLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/dashboard" element={<Dashboard />} />
                <Route path="/dashboard/billing" element={<Billing />} />
                <Route path="/dashboard/wallet" element={<Wallet />} />
                <Route path="/dashboard/channels" element={<Channels />} />
              </Route>

              {/* (admin) — ADMIN only */}
              <Route
                element={
                  <ProtectedRoute requireRole="ADMIN">
                    <AdminLayout />
                  </ProtectedRoute>
                }
              >
                <Route path="/admin" element={<AdminDashboard />} />
                <Route path="/admin/clients" element={<AdminClients />} />
                <Route path="/admin/billing" element={<AdminBilling />} />
                <Route path="/admin/quotas" element={<AdminQuotas />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </div>
      </AuthProvider>
    </LanguageProvider>
  );
}

export default App;
