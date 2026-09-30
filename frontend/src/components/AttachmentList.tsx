import AttachFileOutlined from "@mui/icons-material/AttachFileOutlined";
import DownloadOutlined from "@mui/icons-material/DownloadOutlined";
import PictureAsPdfOutlined from "@mui/icons-material/PictureAsPdfOutlined";
import { Box, Button, ButtonBase, Dialog, IconButton, Skeleton, Stack, Typography } from "@mui/material";
import { useEffect, useState } from "react";
import { apiBlob } from "../api/client";
import type { Attachment } from "../api/types";
import { downloadAttachment } from "../lib/download";
import { sys } from "../theme/scheme";
import { typescale } from "../theme/tokens";

/** Fetches an attachment's bytes once, authenticated (a plain <img>/<iframe>
 * src can't carry the bearer token), and revokes the object URL when the
 * caller is done with it - unlike lib/download.ts's fixed 30s timer, which
 * only suits that fire-and-forget save-file flow. */
function useAttachmentBlob(id: number, enabled: boolean, onError?: () => void) {
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    apiBlob(`/attachments/${id}`)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
        onError?.();
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // Re-run only when the attachment or visibility changes - not when the
    // caller passes a fresh onError closure each render.
  }, [id, enabled]);
  return { url, failed };
}

function DownloadIconButton({ a, onError }: { a: Attachment; onError?: () => void }) {
  return (
    <IconButton
      size="small"
      aria-label={`Download ${a.filename}`}
      onClick={() => downloadAttachment(a.id, a.filename).catch(() => onError?.())}
    >
      <DownloadOutlined fontSize="small" />
    </IconButton>
  );
}

function ImageAttachment({ a, onError }: { a: Attachment; onError?: () => void }) {
  const [open, setOpen] = useState(false);
  const { url, failed } = useAttachmentBlob(a.id, true, onError);

  return (
    <Stack direction="row" sx={{ alignItems: "center", gap: 0.25 }}>
      <ButtonBase
        onClick={() => url && setOpen(true)}
        aria-label={`View ${a.filename}`}
        sx={{
          width: 56,
          height: 56,
          borderRadius: "var(--md-sys-shape-corner-small)",
          overflow: "hidden",
          bgcolor: sys("surfaceContainerHigh"),
          flexShrink: 0,
        }}
      >
        {url ? (
          <Box component="img" src={url} alt="" sx={{ width: "100%", height: "100%", objectFit: "cover" }} />
        ) : failed ? (
          <AttachFileOutlined sx={{ color: sys("onSurfaceVariant") }} />
        ) : (
          <Skeleton variant="rectangular" width="100%" height="100%" />
        )}
      </ButtonBase>
      <DownloadIconButton a={a} onError={onError} />
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="lg" aria-label={a.filename}>
        {url ? (
          <Box component="img" src={url} alt={a.filename} sx={{ display: "block", maxWidth: "90vw", maxHeight: "85vh" }} />
        ) : null}
      </Dialog>
    </Stack>
  );
}

function PdfAttachment({ a, onError }: { a: Attachment; onError?: () => void }) {
  const [open, setOpen] = useState(false);
  const { url, failed } = useAttachmentBlob(a.id, open);
  useEffect(() => {
    if (failed) onError?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [failed]);

  return (
    <Stack direction="row" sx={{ alignItems: "center", gap: 0.25 }}>
      <ButtonBase
        onClick={() => setOpen(true)}
        aria-label={`View ${a.filename}`}
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.5,
          height: 32,
          px: 1.25,
          borderRadius: "var(--md-sys-shape-corner-full)",
          border: `1px solid ${sys("outline")}`,
          color: sys("onSurfaceVariant"),
          ...typescale("label-large"),
        }}
      >
        <PictureAsPdfOutlined fontSize="small" />
        {a.filename}
      </ButtonBase>
      <DownloadIconButton a={a} onError={onError} />
      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="lg" fullWidth aria-label={a.filename}>
        {url ? (
          <Box component="iframe" src={url} title={a.filename} sx={{ width: "100%", height: "85vh", border: "none" }} />
        ) : failed ? (
          <Box sx={{ p: 4 }}>
            <Typography variant="bodyMedium">Couldn't open this file.</Typography>
          </Box>
        ) : (
          <Box sx={{ p: 4 }}>
            <Typography variant="bodyMedium">Loading…</Typography>
          </Box>
        )}
      </Dialog>
    </Stack>
  );
}

function PlainAttachment({ a, onError }: { a: Attachment; onError?: () => void }) {
  return (
    <Button
      size="small"
      startIcon={<AttachFileOutlined />}
      onClick={() => downloadAttachment(a.id, a.filename).catch(() => onError?.())}
    >
      {a.filename}
    </Button>
  );
}

/** Images preview inline with a lightbox; PDFs open in an embedded viewer;
 * everything else stays a direct download. Every attachment keeps an
 * explicit download action regardless of type. */
export function AttachmentList({ attachments, onError }: { attachments: Attachment[]; onError?: () => void }) {
  if (!attachments.length) return null;
  return (
    <Stack direction="row" sx={{ flexWrap: "wrap", gap: 1, alignItems: "center" }}>
      {attachments.map((a) =>
        a.content_type.startsWith("image/") ? (
          <ImageAttachment key={a.id} a={a} onError={onError} />
        ) : a.content_type === "application/pdf" ? (
          <PdfAttachment key={a.id} a={a} onError={onError} />
        ) : (
          <PlainAttachment key={a.id} a={a} onError={onError} />
        ),
      )}
    </Stack>
  );
}
