import { Box, Button, Chip, Stack, TextField, Typography } from "@mui/material";
import { ThemeMenu } from "../components/ThemeMenu";
import { toCamel } from "../theme/muiTheme";
import { COLOR_ROLES, SEED, sys, type ColorRole } from "../theme/scheme";
import { useThemeController } from "../theme/ThemeController";
import { SHAPE, TYPESCALE, type TypeRoleName } from "../theme/tokens";

const PAIRS: [ColorRole, ColorRole][] = [
  ["primary", "onPrimary"],
  ["primaryContainer", "onPrimaryContainer"],
  ["secondary", "onSecondary"],
  ["secondaryContainer", "onSecondaryContainer"],
  ["tertiary", "onTertiary"],
  ["tertiaryContainer", "onTertiaryContainer"],
  ["error", "onError"],
  ["errorContainer", "onErrorContainer"],
  ["surface", "onSurface"],
  ["surfaceContainerLowest", "onSurface"],
  ["surfaceContainerLow", "onSurface"],
  ["surfaceContainer", "onSurface"],
  ["surfaceContainerHigh", "onSurface"],
  ["surfaceContainerHighest", "onSurface"],
  ["surfaceContainerHighest", "onSurfaceVariant"],
  ["inverseSurface", "inverseOnSurface"],
];

/** Dev-only: every colour role pair and type role, for screenshot critique. */
export function TokensPage() {
  const { scheme, isDark, contrast } = useThemeController();
  const unpaired = COLOR_ROLES.filter((r) => !PAIRS.some(([bg, fg]) => bg === r || fg === r));

  return (
    <Box sx={{ bgcolor: sys("surface"), color: sys("onSurface"), minHeight: "100dvh", p: { xs: 2, md: 4 } }}>
      <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between", mb: 3 }}>
        <Box>
          <Typography variant="headlineMedium">Design tokens</Typography>
          <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
            Seed {SEED}, SchemeContent, {isDark ? "dark" : "light"}, contrast {contrast}
          </Typography>
        </Box>
        <ThemeMenu />
      </Stack>

      <Typography variant="titleMedium" component="h2" sx={{ mb: 1.5 }}>
        Colour role pairs
      </Typography>
      <Box sx={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: 1, mb: 2 }}>
        {PAIRS.map(([bg, fg]) => (
          <Box
            key={`${bg}-${fg}`}
            data-role={bg}
            sx={{ bgcolor: sys(bg), color: sys(fg), p: 1.5, borderRadius: "var(--md-sys-shape-corner-small)", border: `1px solid ${sys("outlineVariant")}` }}
          >
            <Typography variant="labelLarge" component="div">
              {bg}
            </Typography>
            <Typography variant="bodySmall" component="div" className="tabular">
              {fg} on {scheme[bg]}
            </Typography>
          </Box>
        ))}
      </Box>
      <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1, mb: 4 }}>
        {unpaired.map((role) => (
          <Box key={role} sx={{ display: "flex", alignItems: "center", gap: 1, pr: 1.5 }}>
            <Box sx={{ width: 24, height: 24, bgcolor: sys(role), borderRadius: "var(--md-sys-shape-corner-extra-small)", border: `1px solid ${sys("outlineVariant")}` }} />
            <Typography variant="bodySmall" className="tabular">
              {role} {scheme[role]}
            </Typography>
          </Box>
        ))}
      </Stack>

      <Typography variant="titleMedium" component="h2" sx={{ mb: 1.5 }}>
        Type roles
      </Typography>
      <Stack spacing={1} sx={{ mb: 4 }}>
        {(Object.keys(TYPESCALE) as TypeRoleName[]).map((role) => (
          <Stack key={role} direction="row" spacing={2} sx={{ alignItems: "baseline" }}>
            <Typography variant="labelSmall" sx={{ width: 120, flexShrink: 0, color: sys("onSurfaceVariant") }}>
              {role}
            </Typography>
            <Typography variant={toCamel(role)} sx={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              Charged twice for March, TCK-01042
            </Typography>
          </Stack>
        ))}
        <Typography variant="bodyMedium" className="tabular">
          Tabular figures: 00:14:07 01:11:59 TCK-01042
        </Typography>
      </Stack>

      <Typography variant="titleMedium" component="h2" sx={{ mb: 1.5 }}>
        Shape and components
      </Typography>
      <Stack direction="row" sx={{ flexWrap: "wrap", gap: 2, alignItems: "center", mb: 3 }}>
        {Object.keys(SHAPE).map((token) => (
          <Box key={token} sx={{ textAlign: "center" }}>
            <Box sx={{ width: 64, height: 40, bgcolor: sys("secondaryContainer"), borderRadius: `var(--md-sys-shape-corner-${token})` }} />
            <Typography variant="labelSmall">{token}</Typography>
          </Box>
        ))}
      </Stack>
      <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1.5, alignItems: "center" }}>
        <Button variant="contained">Filled</Button>
        <Button variant="outlined">Outlined</Button>
        <Button variant="text">Text</Button>
        <Button variant="tonal">Tonal</Button>
        <Chip label="Filter chip" />
        <Chip label="Outlined chip" variant="outlined" />
        <TextField label="Text field" size="small" />
      </Stack>
    </Box>
  );
}
