import { Alert, Box, Button, Link, Stack, TextField, Typography } from "@mui/material";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError, errorMessage } from "../api/client";
import type { MfaChallenge, MfaEnabled, MfaSetup, User } from "../api/types";
import { sys } from "../theme/scheme";
import { typescale } from "../theme/tokens";
import { useAuth } from "./AuthContext";
import { AuthLayout } from "./AuthLayout";

type Props = { challenge: MfaChallenge; onDone: (user: User) => void; onRestart: () => void };

/** The second sign-in step, for every account: set up an authenticator the
 * first time, then enter its code each time. */
export function TwoStep({ challenge, onDone, onRestart }: Props) {
  const [enabled, setEnabled] = useState<MfaEnabled | null>(null);
  if (enabled) return <RecoveryCodes enabled={enabled} onDone={onDone} />;
  return challenge.mfa === "enroll" ? (
    <Enroll mfaToken={challenge.mfa_token} onEnabled={setEnabled} onRestart={onRestart} />
  ) : (
    <Verify mfaToken={challenge.mfa_token} onDone={onDone} onRestart={onRestart} />
  );
}

function ErrorAlert({ error, onRestart }: { error: { message: string; expired: boolean }; onRestart: () => void }) {
  return (
    <Alert
      severity="error"
      variant="filled"
      sx={{ bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}
      action={
        error.expired ? (
          <Button color="inherit" size="small" onClick={onRestart}>
            Sign in again
          </Button>
        ) : undefined
      }
    >
      {error.message}
    </Alert>
  );
}

// A 401 that isn't about the code means the 5-minute sign-in token expired.
function describe(err: unknown) {
  const message = errorMessage(err);
  return { message, expired: err instanceof ApiError && err.status === 401 && message.includes("expired") };
}

function CodeField({
  value,
  onChange,
  recovery = false,
  invalid,
}: {
  value: string;
  onChange: (v: string) => void;
  recovery?: boolean;
  invalid: boolean;
}) {
  return (
    <TextField
      label={recovery ? "Recovery code" : "6-digit code"}
      value={value}
      onChange={(e) => onChange(recovery ? e.target.value : e.target.value.replace(/\D/g, "").slice(0, 6))}
      autoComplete="one-time-code"
      autoFocus
      fullWidth
      required
      error={invalid}
      helperText={invalid ? (recovery ? "Enter one of your recovery codes" : "Enter the 6 digits from your app") : undefined}
      slotProps={{
        htmlInput: recovery
          ? { autoCapitalize: "none", spellCheck: false }
          : { inputMode: "numeric", pattern: "[0-9]*", maxLength: 6 },
      }}
      sx={{ "& input": { ...typescale("title-large"), fontVariantNumeric: "tabular-nums", letterSpacing: recovery ? 0 : "0.2em" } }}
    />
  );
}

function Verify({ mfaToken, onDone, onRestart }: { mfaToken: string; onDone: (u: User) => void; onRestart: () => void }) {
  const { verifyTwoStep } = useAuth();
  const [recovery, setRecovery] = useState(false);
  const [code, setCode] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ReturnType<typeof describe> | null>(null);
  const invalid = submitted && (recovery ? code.trim().length < 10 : code.length !== 6);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (recovery ? code.trim().length < 10 : code.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      onDone(await verifyTwoStep(mfaToken, code.trim()));
    } catch (err) {
      setError(describe(err));
      setCode("");
      setSubmitted(false);
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Enter your code"
      intro={
        recovery
          ? "Each recovery code signs you in once. After using one, ask an admin to reset two-step verification if you've lost your phone."
          : "Open your authenticator app and enter the current 6-digit code for LiverX Help Desk."
      }
    >
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={2.5}>
          {error ? <ErrorAlert error={error} onRestart={onRestart} /> : null}
          <CodeField key={String(recovery)} value={code} onChange={setCode} recovery={recovery} invalid={invalid} />
          <Button type="submit" variant="contained" size="large" disabled={busy} sx={{ alignSelf: "flex-start" }}>
            {busy ? "Checking…" : "Verify"}
          </Button>
          <Typography variant="bodyMedium" sx={{ color: sys("onSurfaceVariant") }}>
            <Link
              component="button"
              type="button"
              onClick={() => {
                setRecovery(!recovery);
                setCode("");
                setSubmitted(false);
              }}
              sx={{ ...typescale("body-medium"), verticalAlign: "baseline" }}
            >
              {recovery ? "Use your authenticator app instead" : "Use a recovery code instead"}
            </Link>
          </Typography>
        </Stack>
      </Box>
    </AuthLayout>
  );
}

function Enroll({
  mfaToken,
  onEnabled,
  onRestart,
}: {
  mfaToken: string;
  onEnabled: (e: MfaEnabled) => void;
  onRestart: () => void;
}) {
  const { setupTwoStep, enableTwoStep } = useAuth();
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ReturnType<typeof describe> | null>(null);
  // Every setup call makes a new secret, so ask once per sign-in token (not
  // again on StrictMode's second effect run), or the QR could be stale.
  const requested = useRef<string | null>(null);

  useEffect(() => {
    if (requested.current === mfaToken) return;
    requested.current = mfaToken;
    setupTwoStep(mfaToken)
      .then(setSetup)
      .catch((err) => setError(describe(err)));
  }, [mfaToken, setupTwoStep]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (code.length !== 6) return;
    setBusy(true);
    setError(null);
    try {
      onEnabled(await enableTwoStep(mfaToken, code));
    } catch (err) {
      setError(describe(err));
      setCode("");
      setSubmitted(false);
      setBusy(false);
    }
  }

  return (
    <AuthLayout
      title="Set up two-step verification"
      intro="Every LiverX Help Desk account signs in with a password and a code from an authenticator app, like Google Authenticator or Microsoft Authenticator. It takes a minute, once."
    >
      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={2.5}>
          {error ? <ErrorAlert error={error} onRestart={onRestart} /> : null}
          <Box component="ol" sx={{ m: 0, pl: 2.5, display: "grid", gap: 2.5, "& > li::marker": { ...typescale("title-small") } }}>
            <li>
              <Typography variant="titleSmall" component="p">
                Scan this QR code with your app
              </Typography>
              <Box
                sx={{
                  mt: 1.5,
                  width: 196,
                  height: 196,
                  borderRadius: "var(--md-sys-shape-corner-large)",
                  overflow: "hidden",
                  bgcolor: sys("surfaceContainerHighest"),
                }}
              >
                {setup ? (
                  <Box
                    component="img"
                    src={setup.qr_svg_data_uri}
                    alt="QR code for setting up two-step verification"
                    sx={{ display: "block", width: "100%", height: "100%" }}
                  />
                ) : null}
              </Box>
              <Typography variant="bodyMedium" sx={{ mt: 1.5, color: sys("onSurfaceVariant") }}>
                Can't scan it? Add this key in the app instead:
              </Typography>
              <Typography
                variant="titleMedium"
                component="p"
                aria-label="Setup key"
                sx={{ mt: 0.5, fontVariantNumeric: "tabular-nums", overflowWrap: "anywhere", userSelect: "all" }}
              >
                {setup ? setup.secret.match(/.{1,4}/g)?.join(" ") : "…"}
              </Typography>
            </li>
            <li>
              <Typography variant="titleSmall" component="p" sx={{ mb: 1.5 }}>
                Enter the code it shows
              </Typography>
              <CodeField value={code} onChange={setCode} invalid={submitted && code.length !== 6} />
            </li>
          </Box>
          <Button type="submit" variant="contained" size="large" disabled={busy || !setup} sx={{ alignSelf: "flex-start" }}>
            {busy ? "Turning on…" : "Turn on two-step verification"}
          </Button>
        </Stack>
      </Box>
    </AuthLayout>
  );
}

function RecoveryCodes({ enabled, onDone }: { enabled: MfaEnabled; onDone: (u: User) => void }) {
  const { accept } = useAuth();
  const [copied, setCopied] = useState(false);

  return (
    <AuthLayout
      title="Save your recovery codes"
      intro="If you lose your phone, each code signs you in once. Keep them somewhere safe, like a password manager. We won't show them again."
    >
      <Stack spacing={2.5}>
        <Box
          component="ul"
          aria-label="Recovery codes"
          sx={{
            listStyle: "none",
            m: 0,
            p: 2,
            display: "grid",
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gap: 1,
            borderRadius: "var(--md-sys-shape-corner-large)",
            bgcolor: sys("surfaceContainerHighest"),
            ...typescale("title-medium"),
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {enabled.recovery_codes.map((c) => (
            <li key={c}>{c}</li>
          ))}
        </Box>
        <Stack direction="row" sx={{ gap: 1, flexWrap: "wrap" }}>
          <Button variant="contained" size="large" onClick={() => onDone(accept(enabled))}>
            I've saved them, continue
          </Button>
          <Button
            size="large"
            onClick={() =>
              navigator.clipboard
                ?.writeText(enabled.recovery_codes.join("\n"))
                .then(() => setCopied(true))
                .catch(() => undefined)
            }
          >
            {copied ? "Copied" : "Copy codes"}
          </Button>
        </Stack>
      </Stack>
    </AuthLayout>
  );
}
