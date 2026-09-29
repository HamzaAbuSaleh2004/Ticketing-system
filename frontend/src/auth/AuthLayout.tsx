import { Box, Typography } from "@mui/material";
import type { ReactNode } from "react";
import { LiverXWordmark } from "../components/Logo";
import { ThemeMenu } from "../components/ThemeMenu";
import { sys } from "../theme/scheme";

/** Sign-in / register: a left-aligned headline beside the form (stacked on
 * compact windows), in the end-user portal's calm style. */
export function AuthLayout({ title, intro, children }: { title: string; intro: string; children: ReactNode }) {
  return (
    <Box sx={{ minHeight: "100dvh", bgcolor: sys("surface"), display: "flex", flexDirection: "column" }}>
      <Box
        component="header"
        sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", px: { xs: 2, sm: 3 }, height: 64 }}
      >
        <LiverXWordmark />
        <ThemeMenu />
      </Box>
      <Box
        component="main"
        sx={{
          flex: 1,
          display: "grid",
          alignContent: "start",
          gap: { xs: 4, md: 8 },
          gridTemplateColumns: { xs: "1fr", md: "minmax(0, 1fr) minmax(0, 440px)" },
          width: "100%",
          maxWidth: 1040,
          mx: "auto",
          px: { xs: 2, sm: 3 },
          pt: { xs: 4, md: 12 },
          pb: 6,
        }}
      >
        <Box>
          <Typography variant="displaySmall" sx={{ fontSize: { xs: "var(--md-sys-typescale-headline-large-size)", md: undefined } }}>
            {title}
          </Typography>
          <Typography variant="bodyLarge" sx={{ mt: 2, color: sys("onSurfaceVariant"), maxWidth: 420 }}>
            {intro}
          </Typography>
        </Box>
        <Box
          sx={{
            bgcolor: sys("surfaceContainerLow"),
            borderRadius: "var(--md-sys-shape-corner-extra-large)",
            p: { xs: 3, sm: 4 },
          }}
        >
          {children}
        </Box>
      </Box>
    </Box>
  );
}
