import { Box } from "@mui/material";
import wordmarkUrl from "../assets/brand/liverx-logo.svg";
import iconUrl from "../assets/brand/liverx-icon.png";
import { useThemeController } from "../theme/ThemeController";

/** The colour wordmark reads fine directly on a light surface (page 4 of the
 * brand guideline explicitly allows "colour logo on white"), but its black
 * blade nearly disappears against our dark surface, so dark mode gets it on
 * a fixed light card instead of recolouring the mark. */
export function LiverXWordmark({ height = 28 }: { height?: number }) {
  const { isDark } = useThemeController();
  const img = <img src={wordmarkUrl} alt="LiverX" style={{ height, width: "auto", display: "block" }} />;
  if (!isDark) return img;
  return (
    <Box sx={{ bgcolor: "#ffffff", borderRadius: "var(--md-sys-shape-corner-small)", px: 1, py: 0.5, display: "inline-flex" }}>
      {img}
    </Box>
  );
}

/** The X icon alone, for tight spaces (the agent nav rail). Same dark-mode
 * treatment as the wordmark, for the same reason. */
export function LiverXIcon({ size = 32 }: { size?: number }) {
  const { isDark } = useThemeController();
  const img = <img src={iconUrl} alt="LiverX" style={{ height: size, width: "auto", display: "block" }} />;
  if (!isDark) return img;
  return (
    <Box sx={{ bgcolor: "#ffffff", borderRadius: "var(--md-sys-shape-corner-small)", p: 0.5, display: "inline-flex" }}>
      {img}
    </Box>
  );
}
