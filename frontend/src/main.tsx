import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import Home from "./pages/Home";
import WinbackPage from "./pages/WinbackPage";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/w/:token" element={<WinbackPage />} />
      </Routes>
    </BrowserRouter>
  </StrictMode>,
);
