import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import { ProveedorEstado } from "./state";
import "./styles/tokens.css";
import "./styles/base.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ProveedorEstado>
      <App />
    </ProveedorEstado>
  </StrictMode>,
);
