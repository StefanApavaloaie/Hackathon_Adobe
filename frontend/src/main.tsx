// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./styles/tokens.css";
import "./styles/base.css";

import RequireLogin from "./components/RequireLogin";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import ThanksPage from "./pages/ThanksPage";
import WinbackPage from "./pages/WinbackPage";

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
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
