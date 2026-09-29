import { Alert, Box, Button, Link, Stack, TextField, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, Navigate, useNavigate } from "react-router-dom";
import { useAuthConfig } from "../api/hooks";
import { ApiError, errorMessage } from "../api/client";
import type { MfaChallenge } from "../api/types";
import { sys } from "../theme/scheme";
import { homeFor, useAuth } from "./AuthContext";
import { AuthLayout } from "./AuthLayout";
import { TwoStep } from "./TwoStep";

export const MIN_PASSWORD = 8;

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const authConfig = useAuthConfig();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null);

  if (user) return <Navigate to={homeFor(user.role)} replace />;
  if (authConfig.data?.allow_registration === false) {
    return (
      <AuthLayout title="Registration is closed" intro="Ask an admin to create your account, then sign in below.">
        <Button component={RouterLink} to="/login" variant="contained" size="large">
          Go to sign in
        </Button>
      </AuthLayout>
    );
  }
  if (challenge) {
    return (
      <TwoStep
        challenge={challenge}
        onDone={(created) => navigate(homeFor(created.role), { replace: true })}
        // The account exists now; if setup lapses, finish it by signing in.
        onRestart={() => navigate("/login", { replace: true })}
      />
    );
  }

  const passwordTooShort = (submitted || password.length > 0) && password.length < MIN_PASSWORD;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (!name.trim() || !email || password.length < MIN_PASSWORD) return;
    setBusy(true);
    setError(null);
    try {
      setChallenge(await register(name.trim(), email, password));
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 409
          ? "An account with this email already exists. Sign in instead."
          : errorMessage(err),
      );
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Create your account"
      intro="One account for every request you send us, so you can follow each one to the end."
    >
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={2.5}>
          {error ? (
            <Alert severity="error" variant="filled" sx={{ bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
              {error}
            </Alert>
          ) : null}
          <TextField label="Name" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} required autoFocus fullWidth error={submitted && !name.trim()} helperText={submitted && !name.trim() ? "Enter your name" : undefined} />
          <TextField
            label="Email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            fullWidth
            error={submitted && !email}
            helperText={submitted && !email ? "Enter your email" : undefined}
          />
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            fullWidth
            error={passwordTooShort}
            helperText={`At least ${MIN_PASSWORD} characters`}
          />
          <Button
            type="submit"
            variant="contained"
            size="large"
            disabled={busy}
            sx={{ alignSelf: "flex-start" }}
          >
            {busy ? "Creating account…" : "Create account"}
          </Button>
          <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
            Already have an account?{" "}
            <Link component={RouterLink} to="/login">
              Sign in
            </Link>
          </Typography>
        </Stack>
      </Box>
    </AuthLayout>
  );
}
