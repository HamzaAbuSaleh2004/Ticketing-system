import { Box, Button, Skeleton, Typography } from "@mui/material";
import { keyframes } from "@mui/system";
import { Link as RouterLink } from "react-router-dom";
import type { KbSearch } from "../../api/types";
import { sys } from "../../theme/scheme";
import { typescale } from "../../theme/tokens";

// The portal's one orchestrated moment: the results arriving.
const reveal = keyframes`
  from { opacity: 0; transform: scale(0.985); }
  to { opacity: 1; transform: none; }
`;

const onContainerMix = (pct: number) =>
  `color-mix(in srgb, ${sys("onPrimaryContainer")} ${pct}%, transparent)`;

const requestLink = (q: string) => `/requests/new?subject=${encodeURIComponent(q.slice(0, 200))}`;

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

type Props = { q: string; data: KbSearch | undefined; isLoading: boolean; error: unknown };

/** Help articles matching the search, best match first. */
export function KbResults({ q, data, isLoading, error }: Props) {
  if (isLoading) {
    return (
      <Box
        aria-busy="true"
        aria-label="Searching help articles"
        sx={{ bgcolor: sys("surfaceContainerLow"), borderRadius: "var(--md-sys-shape-corner-extra-large-increased)", p: { xs: 3, sm: 4 } }}
      >
        {[60, 92, 48, 84].map((w) => (
          <Skeleton key={w} variant="text" width={`${w}%`} sx={{ bgcolor: sys("surfaceContainerHighest"), fontSize: "1.25rem" }} />
        ))}
      </Box>
    );
  }

  if (error) {
    return <QuietPanel q={q} title="Search didn't work" body="You can still send us a request and our team will reply." />;
  }

  if (!data) return null;

  if (data.results.length === 0) {
    return (
      <QuietPanel
        q={q}
        title="No help article matches this yet"
        body="Send us a request with the details and our team will reply."
      />
    );
  }

  const count = data.results.length;

  return (
    <Box
      component="section"
      aria-labelledby="kb-results-title"
      sx={{
        bgcolor: sys("primaryContainer"),
        color: sys("onPrimaryContainer"),
        borderRadius: "var(--md-sys-shape-corner-extra-large-increased)",
        p: { xs: 3, sm: 4 },
        animation: `${reveal} var(--md-sys-motion-duration-medium4) var(--md-sys-motion-easing-emphasized-decelerate)`,
        "@media (prefers-reduced-motion: reduce)": { animation: "none" },
      }}
    >
      <Typography id="kb-results-title" variant="titleMedium" component="h2">
        {count === 1 ? "1 help article matches" : `${count} help articles match`}
      </Typography>

      <Box component="ul" sx={{ listStyle: "none", p: 0, m: 0, mt: 1.5 }}>
        {data.results.map((r) => (
          <Box component="li" key={r.id} sx={{ "& + &": { borderTop: `1px solid ${onContainerMix(20)}` } }}>
            <Box
              component={RouterLink}
              to={`/help/${r.slug}`}
              sx={{
                display: "block",
                py: 1.75,
                px: 1.5,
                mx: -1.5,
                borderRadius: "var(--md-sys-shape-corner-large)",
                color: "inherit",
                textDecoration: "none",
                transition: "background-color var(--md-sys-motion-duration-short4) var(--md-sys-motion-easing-standard)",
                "&:hover": { bgcolor: onContainerMix(8) },
                "&:hover .kb-title": { textDecoration: "underline" },
                "&:focus-visible": { outline: `2px solid ${sys("onPrimaryContainer")}`, outlineOffset: -2 },
              }}
            >
              <Box component="span" className="kb-title" sx={{ display: "block", ...typescale("title-medium") }}>
                {r.title}
              </Box>
              <Box component="span" sx={{ display: "block", mt: 0.5, maxWidth: "68ch", ...typescale("body-medium") }}>
                {r.snippet}
              </Box>
            </Box>
          </Box>
        ))}
      </Box>

      <Box
        sx={{
          mt: 1.5,
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
          Didn't find what you need?
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
