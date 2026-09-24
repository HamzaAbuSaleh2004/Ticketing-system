import AddOutlined from "@mui/icons-material/AddOutlined";
import { Box, Button, Stack, Typography } from "@mui/material";
import { Link as RouterLink, useSearchParams } from "react-router-dom";
import { MIN_QUERY, useKbSearch, useMyTickets } from "../../api/hooks";
import { KbAnswerPanel } from "./KbAnswerPanel";
import { RequestList } from "./RequestList";
import { SearchBar } from "./SearchBar";

export function HomePage() {
  const [params, setParams] = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const search = useKbSearch(q);
  const tickets = useMyTickets();

  return (
    <Box sx={{ pt: { xs: 3, sm: 6 } }}>
      <Typography variant="headlineLarge" component="h1" sx={{ mb: 3 }}>
        How can we help?
      </Typography>
      <SearchBar value={q} onSearch={(next) => setParams(next ? { q: next } : {}, { replace: false })} />

      {q.length >= MIN_QUERY ? (
        <Box sx={{ mt: 3 }} aria-live="polite">
          <KbAnswerPanel q={q} data={search.data} isLoading={search.isFetching && !search.data} error={search.error} />
        </Box>
      ) : null}

      <Stack
        direction="row"
        component="section"
        aria-labelledby="your-requests"
        sx={{ mt: { xs: 5, sm: 7 }, mb: 1, alignItems: "center", justifyContent: "space-between", gap: 2 }}
      >
        <Typography id="your-requests" variant="titleLarge" component="h2">
          Your requests
        </Typography>
        <Button
          component={RouterLink}
          to="/requests/new"
          startIcon={<AddOutlined />}
          variant="tonal"
        >
          New request
        </Button>
      </Stack>
      <RequestList
        items={tickets.data?.items}
        isLoading={tickets.isLoading}
        isError={tickets.isError}
        onRetry={() => tickets.refetch()}
      />
    </Box>
  );
}
