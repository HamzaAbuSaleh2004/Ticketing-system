import "@fontsource-variable/google-sans-flex/rond.css";
import "@fontsource-variable/roboto-flex/opsz.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { router } from "./routes";
import { ThemeController } from "./theme/ThemeController";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: true } },
});

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <ThemeController>
          <RouterProvider router={router} />
        </ThemeController>
      </AuthProvider>
    </QueryClientProvider>
  </StrictMode>,
);
