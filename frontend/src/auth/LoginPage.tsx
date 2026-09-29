import { Alert, Box, Button, Link, Stack, TextField, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, errorMessage } from "../api/client";
import type { MfaChallenge } from "../api/types";
import { sys } from "../theme/scheme";
import { homeFor, useAuth } from "./AuthContext";
import { AuthLayout } from "./AuthLayout";
import { TwoStep } from "./TwoStep";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const from = (useLocation().state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null);

  if (user) return <Navigate to={homeFor(user.role)} replace />;
  if (challenge) {
    return (
      <TwoStep
        challenge={challenge}
        onDone={(signedIn) => navigate(from ?? homeFor(signedIn.role), { replace: true })}
        onRestart={() => {
          setChallenge(null);
          setPassword("");
          setBusy(false);
        }}
      />
    );
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (!email || !password) return;
    setBusy(true);
    setError(null);
    try {
      setChallenge(await login(email, password));
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 401
          ? "That email and password don't match an account."
          : errorMessage(err),
      );
      setBusy(false);
    }
  }

  return (
    <AuthLayout title="Sign in" intro="Track your requests and find answers in our help articles.">
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={2.5}>
          {error ? (
            <Alert severity="error" variant="filled" sx={{ bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
              {error}
            </Alert>
          ) : null}
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            fullWidth
            error={submitted && !email}
            helperText={submitted && !email ? "Enter your email" : undefined}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            fullWidth
            error={submitted && !password}
            helperText={submitted && !password ? "Enter your password" : undefined}
          />
          <Button type="submit" variant="contained" size="large" disabled={busy} sx={{ alignSelf: "flex-start" }}>
            {busy ? "Signing in…" : "Sign in"}
          </Button>
          <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
            New here?{" "}
            <Link component={RouterLink} to="/register">
              Create an account
            </Link>
          </Typography>
        </Stack>
      </Box>
    </AuthLayout>
  );
}
