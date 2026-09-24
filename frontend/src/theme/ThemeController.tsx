import { CssBaseline, GlobalStyles, ThemeProvider, useMediaQuery, useTheme } from "@mui/material";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { buildMuiTheme, type Density } from "./muiTheme";
import { generateScheme, schemeCssVars, type ColorScheme, type Contrast } from "./scheme";
import { staticCssVars } from "./tokens";

export type ThemeMode = "system" | "light" | "dark";

type ThemeState = {
  mode: ThemeMode;
  setMode: (mode: ThemeMode) => void;
  contrast: Contrast;
  setContrast: (contrast: Contrast) => void;
  isDark: boolean;
  scheme: ColorScheme;
};

const ThemeContext = createContext<ThemeState | null>(null);
const STORAGE_KEY = "ticketing.theme";

function readStored(): { mode: ThemeMode; contrast: Contrast } {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    const mode = ["system", "light", "dark"].includes(raw.mode) ? raw.mode : "system";
    const contrast = [0, 0.5, 1].includes(raw.contrast) ? raw.contrast : 0;
    return { mode, contrast };
  } catch {
    return { mode: "system", contrast: 0 };
  }
}

function store(value: { mode: ThemeMode; contrast: Contrast }) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Storage unavailable (private mode, blocked): the choice just isn't remembered.
  }
}

export function ThemeController({ children }: { children: ReactNode }) {
  const [{ mode, contrast }, setState] = useState(readStored);
  const prefersDark = useMediaQuery("(prefers-color-scheme: dark)", { noSsr: true });
  const isDark = mode === "dark" || (mode === "system" && prefersDark);
  const scheme = useMemo(() => generateScheme(isDark, contrast), [isDark, contrast]);

  const value = useMemo<ThemeState>(() => {
    const update = (next: { mode: ThemeMode; contrast: Contrast }) => {
      store(next);
      setState(next);
    };
    return {
      mode,
      contrast,
      isDark,
      scheme,
      setMode: (m) => update({ mode: m, contrast }),
      setContrast: (c) => update({ mode, contrast: c }),
    };
  }, [mode, contrast, isDark, scheme]);

  const rootVars = useMemo(() => ({ ...staticCssVars(), ...schemeCssVars(scheme) }), [scheme]);

  return (
    <ThemeContext.Provider value={value}>
      <DensityScope density="comfortable" root>
        <CssBaseline />
        <GlobalStyles styles={{ ":root": { ...rootVars, colorScheme: isDark ? "dark" : "light" } }} />
        {children}
      </DensityScope>
    </ThemeContext.Provider>
  );
}

export function useThemeController(): ThemeState {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useThemeController must be used inside <ThemeController>");
  return ctx;
}

/** Sets the portal's density and display-type personality (ROND 60 for the
 * calm end-user portal, 0 for the dense agent console) via its MUI theme. */
export function DensityScope({
  density,
  children,
  root = false,
}: {
  density: Density;
  children: ReactNode;
  root?: boolean;
}) {
  const { scheme, isDark } = useThemeController();
  const theme = useMemo(() => buildMuiTheme(scheme, isDark, density), [scheme, isDark, density]);
  return (
    <ThemeProvider theme={theme}>
      {root ? children : <div data-density={density} style={{ display: "contents" }}>{children}</div>}
    </ThemeProvider>
  );
}

export function useDensity(): Density {
  return useTheme().palette.density;
}
