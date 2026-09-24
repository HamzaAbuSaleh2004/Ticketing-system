import AttachFileOutlined from "@mui/icons-material/AttachFileOutlined";
import { Alert, Box, Button, Chip, Stack, TextField, Typography } from "@mui/material";
import { useRef, useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useCreateTicket } from "../../api/hooks";
import { sys } from "../../theme/scheme";

const ACCEPT = ["image/png", "image/jpeg", "image/gif", "application/pdf", "text/plain"];
const MAX_BYTES = 10 * 1024 * 1024;

export function NewRequestPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const create = useCreateTicket();
  const fileInput = useRef<HTMLInputElement>(null);
  const [subject, setSubject] = useState(params.get("subject") ?? "");
  const [description, setDescription] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function pickFile(f: File | undefined) {
    setFileError(null);
    if (!f) return;
    if (!ACCEPT.includes(f.type)) {
      setFileError("Attach a PNG, JPEG, GIF, PDF or plain-text file.");
      return;
    }
    if (f.size > MAX_BYTES) {
      setFileError("That file is over 10 MB. Attach a smaller one.");
      return;
    }
    setFile(f);
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (!subject.trim() || !description.trim()) return;
    create.mutate(
      { subject: subject.trim(), description: description.trim(), file },
      {
        // Failures render from create.isError; mutate() doesn't reject.
        onSuccess: ({ ticket, attachmentError }) =>
          navigate(`/requests/${ticket.id}`, { state: { justCreated: true, attachmentFailed: attachmentError !== null } }),
      },
    );
  }

  return (
    <Box sx={{ pt: { xs: 3, sm: 6 }, maxWidth: 640 }}>
      <Typography variant="headlineLarge" component="h1">
        New request
      </Typography>
      <Typography variant="bodyLarge" sx={{ mt: 1, mb: 4, color: sys("onSurfaceVariant") }}>
        Tell us what's going on. What you expected, what happened instead, and any error message help us answer faster.
      </Typography>

      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={3}>
          {create.isError ? (
            <Alert severity="error" variant="filled" sx={{ bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
              {errorMessage(create.error, "We couldn't send your request. Try again.")}
            </Alert>
          ) : null}
          <TextField
            label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
            fullWidth
            autoFocus={!subject}
            slotProps={{ htmlInput: { maxLength: 255 } }}
            error={submitted && !subject.trim()}
            helperText={submitted && !subject.trim() ? "Add a short subject" : "A few words, like “Charged twice in March”"}
          />
          <TextField
            label="Details"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            fullWidth
            multiline
            minRows={6}
            autoFocus={Boolean(subject)}
            error={submitted && !description.trim()}
            helperText={submitted && !description.trim() ? "Describe the problem so we can help" : undefined}
          />

          <Box>
            <input
              ref={fileInput}
              type="file"
              hidden
              accept={ACCEPT.join(",")}
              onChange={(e) => {
                pickFile(e.target.files?.[0]);
                e.target.value = "";
              }}
            />
            {file ? (
              <Chip
                icon={<AttachFileOutlined />}
                label={file.name}
                onDelete={() => setFile(null)}
                variant="outlined"
                sx={{ maxWidth: "100%" }}
              />
            ) : (
              <Button variant="outlined" startIcon={<AttachFileOutlined />} onClick={() => fileInput.current?.click()}>
                Attach a file
              </Button>
            )}
            <Typography
              variant="bodySmall"
              sx={{ display: "block", mt: 1, color: fileError ? sys("error") : sys("onSurfaceVariant") }}
              role={fileError ? "alert" : undefined}
            >
              {fileError ?? "Optional. Screenshots, PDFs or text files up to 10 MB."}
            </Typography>
          </Box>

          <Stack direction="row" spacing={1}>
            <Button type="submit" variant="contained" size="large" disabled={create.isPending}>
              {create.isPending ? "Sending…" : "Send request"}
            </Button>
            <Button component={RouterLink} to="/" size="large">
              Cancel
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
}
