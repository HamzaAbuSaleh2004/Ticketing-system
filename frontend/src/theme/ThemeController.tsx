import { CssBaseline, GlobalStyles, ThemeProvider, useTheme } from "@mui/material";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { buildMuiTheme, type Density } from "./muiTheme";
import { generateScheme, schemeCssVars, type ColorScheme, type Contrast } from "./scheme";
import { staticCssVars } from "./tokens";

// Phase 25: light only, brand decision - no dark/system mode to choose from.
const isDark = false;

type ThemeState = {
  contrast: Contrast;
  setContrast: (contrast: Contrast) => void;
  isDark: boolean;
  scheme: ColorScheme;
};

const ThemeContext = createContext<ThemeState | null>(null);
const STORAGE_KEY = "ticketing.theme";

function readStored(): { contrast: Contrast } {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
    const contrast = [0, 0.5, 1].includes(raw.contrast) ? raw.contrast : 0;
    return { contrast };
  } catch {
    return { contrast: 0 };
  }
}

function store(value: { contrast: Contrast }) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
  } catch {
    // Storage unavailable (private mode, blocked): the choice just isn't remembered.
  }
}

export function ThemeController({ children }: { children: ReactNode }) {
  const [{ contrast }, setState] = useState(readStored);
  const scheme = useMemo(() => generateScheme(isDark, contrast), [contrast]);

  const value = useMemo<ThemeState>(
    () => ({
      contrast,
      isDark,
      scheme,
      setContrast: (c) => {
        store({ contrast: c });
        setState({ contrast: c });
      },
    }),
    [contrast, scheme],
  );

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
