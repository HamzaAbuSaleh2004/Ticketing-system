import { Box, Button, Typography } from "@mui/material";
import { createBrowserRouter, Link as RouterLink, Outlet, type RouteObject } from "react-router-dom";
import { LoginPage } from "./auth/LoginPage";
import { RegisterPage } from "./auth/RegisterPage";
import { RoleGate } from "./auth/RoleGate";
import { TokensPage } from "./dev/TokensPage";
import { AgentShell } from "./portals/agent/AgentShell";
import { EndUserShell } from "./portals/enduser/EndUserShell";
import { sys } from "./theme/scheme";

function Placeholder({ title }: { title: string }) {
  return (
    <Box sx={{ py: 4, px: { xs: 2, sm: 3 } }}>
      <Typography variant="headlineMedium">{title}</Typography>
    </Box>
  );
}

function NotFound() {
  return (
    <Box sx={{ p: 4, maxWidth: 560, bgcolor: sys("surface"), minHeight: "100dvh" }}>
      <Typography variant="headlineMedium">This page doesn't exist</Typography>
      <Typography variant="bodyLarge" sx={{ my: 2, color: sys("onSurfaceVariant") }}>
        Check the address, or go back to your requests.
      </Typography>
      <Button component={RouterLink} to="/" variant="contained">
        Go to your requests
      </Button>
    </Box>
  );
}

const routes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/register", element: <RegisterPage /> },
  {
    element: (
      <RoleGate roles={["end_user"]}>
        <EndUserShell />
      </RoleGate>
    ),
    children: [{ path: "/", element: <Placeholder title="How can we help?" /> }],
  },
  {
    element: (
      <RoleGate roles={["agent", "admin"]}>
        <AgentShell />
      </RoleGate>
    ),
    children: [
      { path: "/agent", element: <Placeholder title="Queue" /> },
      { path: "/agent/dashboard", element: <Placeholder title="Dashboard" /> },
      {
        element: (
          <RoleGate roles={["admin"]}>
            <Outlet />
          </RoleGate>
        ),
        children: [{ path: "/admin", element: <Placeholder title="Admin" /> }],
      },
    ],
  },
  ...(import.meta.env.DEV ? [{ path: "/_tokens", element: <TokensPage /> }] : []),
  { path: "*", element: <NotFound /> },
];

export const router = createBrowserRouter(routes);
