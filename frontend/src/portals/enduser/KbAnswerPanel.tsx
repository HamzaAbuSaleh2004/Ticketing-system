import { Box, Button, Skeleton, Stack, Typography } from "@mui/material";
import { keyframes } from "@mui/system";
import { Fragment } from "react";
import { Link as RouterLink } from "react-router-dom";
import { ApiError } from "../../api/client";
import type { KbSearchResult, KbSource } from "../../api/types";
import { parseAnswer } from "../../lib/citations";
import { sys } from "../../theme/scheme";
import { typescale } from "../../theme/tokens";

// The portal's one orchestrated moment: the answer arriving.
const reveal = keyframes`
  from { opacity: 0; transform: scale(0.985); }
  to { opacity: 1; transform: none; }
`;

const onContainerMix = (pct: number) =>
  `color-mix(in srgb, ${sys("onPrimaryContainer")} ${pct}%, transparent)`;

const requestLink = (q: string) => `/requests/new?subject=${encodeURIComponent(q.slice(0, 200))}`;

function Marker({ n, source }: { n: number; source: KbSource }) {
  return (
    <Box
      component={RouterLink}
      to={`/help/${source.slug}`}
      aria-label={`Source ${n}: ${source.title}`}
      sx={{
        display: "inline-grid",
        placeItems: "center",
        minWidth: 20,
        height: 20,
        px: 0.5,
        mx: 0.25,
        verticalAlign: "0.1em",
        borderRadius: "var(--md-sys-shape-corner-full)",
        bgcolor: sys("primary"),
        color: sys("onPrimary"),
        textDecoration: "none",
        ...typescale("label-small"),
        fontVariantNumeric: "tabular-nums",
        "&:focus-visible": { outline: `2px solid ${sys("onPrimaryContainer")}`, outlineOffset: 2 },
      }}
    >
      {n}
    </Box>
  );
}

function SourceChip({ n, source }: { n: number; source: KbSource }) {
  return (
    <Box
      component={RouterLink}
      to={`/help/${source.slug}`}
      sx={{
        position: "relative",
        display: "inline-flex",
        alignItems: "center",
        gap: 1,
        minHeight: 40,
        // 48dp touch target around the 40dp chip.
        "&::after": { content: '""', position: "absolute", inset: "-4px 0" },
        pl: 0.75,
        pr: 2,
        borderRadius: "var(--md-sys-shape-corner-full)",
        border: `1px solid ${onContainerMix(45)}`,
        color: sys("onPrimaryContainer"),
        textDecoration: "none",
        ...typescale("label-large"),
        transition: "background-color var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard)",
        "&:hover": { bgcolor: onContainerMix(8) },
        "&:focus-visible": { outline: `2px solid ${sys("onPrimaryContainer")}`, outlineOffset: 2 },
      }}
    >
      <Box
        component="span"
        aria-hidden
        sx={{
          display: "grid",
          placeItems: "center",
          width: 28,
          height: 28,
          borderRadius: "var(--md-sys-shape-corner-full)",
          bgcolor: sys("primary"),
          color: sys("onPrimary"),
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {n}
      </Box>
      {source.title}
    </Box>
  );
}

function QuietPanel({ title, body, q }: { title: string; body: string; q: string }) {
  return (
    <Box
      role="status"
      sx={{ bgcolor: sys("surfaceContainerLow"), borderRadius: "var(--md-sys-shape-corner-extra-large)", p: { xs: 3, sm: 4 } }}
    >
      <Typography variant="titleMedium" component="h2">
        {title}
      </Typography>
      <Typography variant="bodyLarge" sx={{ mt: 0.5, mb: 2.5, color: sys("onSurfaceVariant") }}>
        {body}
      </Typography>
      <Button component={RouterLink} to={requestLink(q)} variant="contained">
        Send a request
      </Button>
    </Box>
  );
}

type Props = { q: string; data: KbSearchResult | undefined; isLoading: boolean; error: unknown };

export function KbAnswerPanel({ q, data, isLoading, error }: Props) {
  if (isLoading) {
    return (
      <Box
        aria-busy="true"
        aria-label="Searching help articles"
        sx={{ bgcolor: sys("surfaceContainerLow"), borderRadius: "var(--md-sys-shape-corner-extra-large-increased)", p: { xs: 3, sm: 4 } }}
      >
        {[96, 88, 60].map((w) => (
          <Skeleton key={w} variant="text" width={`${w}%`} sx={{ bgcolor: sys("surfaceContainerHighest"), fontSize: "1.25rem" }} />
        ))}
        <Stack direction="row" spacing={1} sx={{ mt: 2.5 }}>
          <Skeleton variant="rounded" width={180} height={40} sx={{ bgcolor: sys("surfaceContainerHighest"), borderRadius: "var(--md-sys-shape-corner-full)" }} />
          <Skeleton variant="rounded" width={140} height={40} sx={{ bgcolor: sys("surfaceContainerHighest"), borderRadius: "var(--md-sys-shape-corner-full)" }} />
        </Stack>
      </Box>
    );
  }

  if (error) {
    const unavailable = error instanceof ApiError && error.status === 503;
    return (
      <QuietPanel
        q={q}
        title={unavailable ? "Search isn't available right now" : "Search didn't work"}
        body="You can still send us a request and an agent will reply."
      />
    );
  }

  if (!data) return null;

  if (!data.answer || data.sources.length === 0) {
    return (
      <QuietPanel
        q={q}
        title="No help article answers this yet"
        body="Send us a request with the details and an agent will reply."
      />
    );
  }

  const parts = parseAnswer(data.answer, data.sources.length);
  const count = data.sources.length;

  return (
    <Box
      component="section"
      aria-label="Answer from our help articles"
      sx={{
        bgcolor: sys("primaryContainer"),
        color: sys("onPrimaryContainer"),
        borderRadius: "var(--md-sys-shape-corner-extra-large-increased)",
        p: { xs: 3, sm: 4 },
        animation: `${reveal} var(--md-sys-motion-duration-medium4) var(--md-sys-motion-easing-emphasized-decelerate)`,
        "@media (prefers-reduced-motion: reduce)": { animation: "none" },
      }}
    >
      <Typography variant="bodyLarge" component="p" sx={{ fontSize: { sm: "1.125rem" }, lineHeight: { sm: 1.6 }, maxWidth: "68ch" }}>
        {parts.map((part, i) =>
          part.kind === "text" ? (
            <Fragment key={i}>{part.text}</Fragment>
          ) : (
            <Marker key={i} n={part.n} source={data.sources[part.n - 1]} />
          ),
        )}
      </Typography>

      <Box component="ol" aria-label="Sources" sx={{ listStyle: "none", p: 0, m: 0, mt: 3, display: "flex", flexWrap: "wrap", gap: 1 }}>
        {data.sources.map((source, i) => (
          <li key={source.id}>
            <SourceChip n={i + 1} source={source} />
          </li>
        ))}
      </Box>

      <Box
        sx={{
          mt: 3,
          pt: 2.5,
          borderTop: `1px solid ${onContainerMix(25)}`,
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 1.5,
        }}
      >
        <Typography variant="bodyMedium" sx={{ color: sys("onPrimaryContainer") }}>
          Answered from {count === 1 ? "1 help article" : `${count} help articles`}. Still stuck?
        </Typography>
        <Button
          component={RouterLink}
          to={requestLink(q)}
          sx={{
            bgcolor: sys("onPrimaryContainer"),
            color: sys("primaryContainer"),
            "&:hover": { bgcolor: onContainerMix(88) },
          }}
        >
          Send a request
        </Button>
      </Box>
    </Box>
  );
}
