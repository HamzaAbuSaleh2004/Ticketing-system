import ArrowBackOutlined from "@mui/icons-material/ArrowBackOutlined";
import { Box, Button, Skeleton, Typography } from "@mui/material";
import { Link as RouterLink, useNavigate, useParams } from "react-router-dom";
import { useArticle } from "../../api/hooks";
import { absoluteTime } from "../../lib/tickets";
import { sys } from "../../theme/scheme";

export function ArticlePage() {
  const slug = useParams().slug ?? "";
  const navigate = useNavigate();
  const { data, isLoading, error } = useArticle(slug);

  return (
    <Box component="article" sx={{ pt: { xs: 2, sm: 4 }, maxWidth: "68ch" }}>
      <Button onClick={() => navigate(-1)} startIcon={<ArrowBackOutlined />} sx={{ ml: -1.5, mb: 2 }}>
        Back
      </Button>
      {isLoading ? (
        <>
          <Skeleton width="70%" height={48} />
          <Skeleton />
          <Skeleton />
          <Skeleton width="80%" />
        </>
      ) : error || !data ? (
        <>
          <Typography variant="headlineMedium" component="h1">
            This article isn't available
          </Typography>
          <Button component={RouterLink} to="/" variant="contained" sx={{ mt: 3 }}>
            Search help articles
          </Button>
        </>
      ) : (
        <>
          <Typography variant="headlineLarge" component="h1">
            {data.title}
          </Typography>
          <Typography variant="bodyMedium" sx={{ mt: 1, mb: 3, color: sys("onSurfaceVariant") }}>
            Updated {absoluteTime(data.updated_at)}
          </Typography>
          {data.body.split(/\n{2,}/).map((para, i) => (
            <Typography key={i} variant="bodyLarge" sx={{ mb: 2, lineHeight: 1.65 }}>
              {para}
            </Typography>
          ))}
          <Box sx={{ mt: 4, p: 3, borderRadius: "var(--md-sys-shape-corner-extra-large)", bgcolor: sys("surfaceContainerLow") }}>
            <Typography variant="titleMedium" component="p">
              Didn't solve it?
            </Typography>
            <Typography variant="bodyMedium" sx={{ mt: 0.5, mb: 2, color: sys("onSurfaceVariant") }}>
              Send us a request and an agent will reply.
            </Typography>
            <Button component={RouterLink} to={`/requests/new?subject=${encodeURIComponent(data.title)}`} variant="contained">
              Send a request
            </Button>
          </Box>
        </>
      )}
    </Box>
  );
}
