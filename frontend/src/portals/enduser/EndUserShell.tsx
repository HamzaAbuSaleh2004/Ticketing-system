import { Box, Link, Typography } from "@mui/material";
import { Link as RouterLink, Outlet } from "react-router-dom";
import { AccountMenu } from "../../components/AccountMenu";
import { ThemeMenu } from "../../components/ThemeMenu";
import { sys } from "../../theme/scheme";
import { ROND } from "../../theme/muiTheme";
import { DensityScope } from "../../theme/ThemeController";

/** Calm, comfortable density; one column capped at 880px (PLAN.md §0). */
export function EndUserShell() {
  return (
    <DensityScope density="comfortable">
      <Box sx={{ minHeight: "100dvh", bgcolor: sys("surface") }}>
        <Box
          component="header"
          sx={{
            position: "sticky",
            top: 0,
            zIndex: 10,
            bgcolor: sys("surface"),
            display: "flex",
            alignItems: "center",
            gap: 1,
            px: { xs: 1, sm: 2 },
            height: 64,
          }}
        >
          <Link
            component={RouterLink}
            to="/"
            underline="none"
            sx={{ color: sys("onSurface"), px: 1, py: 1.5, borderRadius: "var(--md-sys-shape-corner-full)" }}
          >
            <Typography variant="titleLarge" component="span" sx={{ fontFamily: "var(--md-sys-typescale-headline-small-font)", fontVariationSettings: `'ROND' ${ROND.comfortable}` }}>
              Support
            </Typography>
          </Link>
          <Box sx={{ flex: 1 }} />
          <ThemeMenu />
          <AccountMenu />
        </Box>
        <Box component="main" sx={{ maxWidth: 880, mx: "auto", px: { xs: 2, sm: 3 }, pb: 8 }}>
          <Outlet />
        </Box>
      </Box>
    </DensityScope>
  );
}
