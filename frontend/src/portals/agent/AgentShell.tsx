import AdminPanelSettingsOutlined from "@mui/icons-material/AdminPanelSettingsOutlined";
import InsightsOutlined from "@mui/icons-material/InsightsOutlined";
import InboxOutlined from "@mui/icons-material/InboxOutlined";
import { Box, ButtonBase, Typography, useMediaQuery } from "@mui/material";
import type { ReactElement } from "react";
import { Link, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { AccountMenu } from "../../components/AccountMenu";
import { ThemeMenu } from "../../components/ThemeMenu";
import { sys } from "../../theme/scheme";
import { DensityScope } from "../../theme/ThemeController";

type NavItem = { to: string; label: string; icon: ReactElement; match: (path: string) => boolean };

function navItems(isAdmin: boolean): NavItem[] {
  const items: NavItem[] = [
    { to: "/agent", label: "Queue", icon: <InboxOutlined />, match: (p) => p === "/agent" || p.startsWith("/agent/tickets") },
    { to: "/agent/dashboard", label: "Dashboard", icon: <InsightsOutlined />, match: (p) => p.startsWith("/agent/dashboard") },
  ];
  if (isAdmin) {
    items.push({ to: "/admin", label: "Admin", icon: <AdminPanelSettingsOutlined />, match: (p) => p.startsWith("/admin") });
  }
  return items;
}

function RailItem({ item, active }: { item: NavItem; active: boolean }) {
  return (
    <ButtonBase
      component={Link}
      to={item.to}
      aria-current={active ? "page" : undefined}
      sx={{
        display: "flex",
        flexDirection: "column",
        gap: 0.5,
        width: 80,
        minHeight: 56,
        py: 0.5,
        borderRadius: "var(--md-sys-shape-corner-large)",
        color: active ? sys("onSurface") : sys("onSurfaceVariant"),
        "&:focus-visible .rail-indicator": { outline: `2px solid ${sys("primary")}`, outlineOffset: 2 },
      }}
    >
      <Box
        className="rail-indicator"
        sx={{
          width: 56,
          height: 32,
          display: "grid",
          placeItems: "center",
          borderRadius: "var(--md-sys-shape-corner-full)",
          bgcolor: active ? sys("secondaryContainer") : "transparent",
          color: active ? sys("onSecondaryContainer") : "inherit",
          transition: "background-color var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard)",
          ".MuiButtonBase-root:hover &": { bgcolor: active ? sys("secondaryContainer") : sys("surfaceContainerHighest") },
        }}
      >
        {item.icon}
      </Box>
      <Typography variant="labelMedium" component="span" sx={{ fontWeight: active ? 700 : 500 }}>
        {item.label}
      </Typography>
    </ButtonBase>
  );
}

/** Dense console: nav rail on medium+ windows, bottom navigation bar on
 * compact ones (M3 navigation by window size class). */
export function AgentShell() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const compact = useMediaQuery("(max-width:599.95px)", { noSsr: true });
  const items = navItems(user?.role === "admin");

  const nav = (
    <Box
      component="nav"
      aria-label="Main"
      sx={
        compact
          ? {
              position: "fixed",
              insetInline: 0,
              bottom: 0,
              height: 80,
              zIndex: 20,
              display: "flex",
              justifyContent: "space-around",
              alignItems: "center",
              bgcolor: sys("surfaceContainer"),
            }
          : {
              width: 80,
              flexShrink: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 1.5,
              pt: 2,
              bgcolor: sys("surfaceContainer"),
              position: "sticky",
              top: 0,
              height: "100dvh",
            }
      }
    >
      {items.map((item) => (
        <RailItem key={item.to} item={item} active={item.match(pathname)} />
      ))}
      {compact ? null : (
        <Box sx={{ mt: "auto", mb: 2, display: "flex", flexDirection: "column", alignItems: "center" }}>
          <ThemeMenu />
          <AccountMenu />
        </Box>
      )}
    </Box>
  );

  return (
    <DensityScope density="compact">
      <Box sx={{ display: "flex", minHeight: "100dvh", bgcolor: sys("surface") }}>
        {nav}
        <Box component="main" sx={{ flex: 1, minWidth: 0, pb: compact ? 10 : 0 }}>
          {compact ? (
            <Box sx={{ display: "flex", justifyContent: "flex-end", px: 1, height: 56, alignItems: "center" }}>
              <ThemeMenu />
              <AccountMenu />
            </Box>
          ) : null}
          <Outlet />
        </Box>
      </Box>
    </DensityScope>
  );
}
