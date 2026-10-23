import "@fontsource-variable/inter";
import "@fontsource-variable/manrope";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./popup.css";
import "./status.css";

createRoot(document.getElementById("root")!).render(<App/>);
