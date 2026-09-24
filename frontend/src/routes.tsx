import { Box, Button, Typography } from "@mui/material";
import { createBrowserRouter, Link as RouterLink, Outlet, useParams, type RouteObject } from "react-router-dom";
import { LoginPage } from "./auth/LoginPage";
import { RegisterPage } from "./auth/RegisterPage";
import { RoleGate } from "./auth/RoleGate";
import { TokensPage } from "./dev/TokensPage";
import { AgentShell } from "./portals/agent/AgentShell";
import { AgentTicketPage } from "./portals/agent/AgentTicketPage";
import { QueuePage } from "./portals/agent/QueuePage";
import { ArticlePage } from "./portals/enduser/ArticlePage";
import { EndUserShell } from "./portals/enduser/EndUserShell";
import { HomePage } from "./portals/enduser/HomePage";
import { NewRequestPage } from "./portals/enduser/NewRequestPage";
import { RequestPage } from "./portals/enduser/RequestPage";
import { sys } from "./theme/scheme";

function Placeholder({ title }: { title: string }) {
  return (
    <Box sx={{ py: 4, px: { xs: 2, sm: 3 } }}>
      <Typography variant="headlineMedium">{title}</Typography>
    </Box>
  );
}

// Keyed by id: moving to another request (a follow-up, a linked parent)
// starts fresh triage polling and shows that request's own toast.
function RequestRoute() {
  const { id } = useParams();
  return <RequestPage key={id} />;
}

function AgentTicketRoute() {
  const { id } = useParams();
  return <AgentTicketPage key={id} />;
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
    children: [
      { path: "/", element: <HomePage /> },
      { path: "/requests/new", element: <NewRequestPage /> },
      { path: "/requests/:id", element: <RequestRoute /> },
      { path: "/help/:slug", element: <ArticlePage /> },
    ],
  },
  {
    element: (
      <RoleGate roles={["agent", "admin"]}>
        <AgentShell />
      </RoleGate>
    ),
    children: [
      { path: "/agent", element: <QueuePage /> },
      { path: "/agent/tickets/:id", element: <AgentTicketRoute /> },
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
