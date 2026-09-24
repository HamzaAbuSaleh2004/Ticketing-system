import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { Role } from "../api/types";
import { homeFor, useAuth } from "./AuthContext";

/** Shows children only to the given roles: signed-out users go to sign-in
 * (and come back afterwards); a signed-in user with another role goes to
 * their own portal. The API enforces the same rules server-side. */
export function RoleGate({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />;
  }
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}
