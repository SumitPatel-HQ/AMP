import { createContext, useContext } from "react";
export const Presentation = createContext<{ mode: "compact" | "expanded"; expand?: () => void }>({ mode: "expanded" });
export const usePanelPresentation = () => useContext(Presentation);
