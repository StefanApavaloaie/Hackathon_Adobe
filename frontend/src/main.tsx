// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes, useParams } from "react-router-dom";

import "./styles/tokens.css";
import "./styles/base.css";

import RequireLogin from "./components/RequireLogin";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import ThanksPage from "./pages/ThanksPage";
import WinbackPage from "./pages/WinbackPage";

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Any other path goes to the dashboard. A bare campaign ID (/<id>) opens that campaign.
function Fallback() {
  const { "*": rest = "" } = useParams();
  const id = rest.replace(/\/+$/, "");
  return <Navigate to={UUID.test(id) ? `/?campaign=${id}` : "/"} replace />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route
          path="/"
          element={
            <RequireLogin>
              <DashboardPage />
            </RequireLogin>
          }
        />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/w/:token" element={<WinbackPage />} />
        <Route path="/thanks" element={<ThanksPage />} />
        <Route path="*" element={<Fallback />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
