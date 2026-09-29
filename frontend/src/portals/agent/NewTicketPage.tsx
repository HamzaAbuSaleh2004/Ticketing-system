import { Alert, Box, Button, MenuItem, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material";
import { useState, type FormEvent } from "react";
import { Link as RouterLink, useNavigate } from "react-router-dom";
import { errorMessage } from "../../api/client";
import { useCreateTicketForCustomer, useOrganizations } from "../../api/hooks";
import type { CustomerSearchResult } from "../../api/types";
import { CustomerPicker } from "../../components/CustomerPicker";
import { sys } from "../../theme/scheme";

type Mode = "existing" | "unclaimed";

/** On behalf of a customer: pick an existing one (immediately claimed), or
 * — if they haven't registered yet — just tag the ticket with their
 * organisation. It's linked to their account later, once they have one. */
export function NewTicketPage() {
  const navigate = useNavigate();
  const create = useCreateTicketForCustomer();
  const organizations = useOrganizations();
  const [mode, setMode] = useState<Mode>("existing");
  const [subject, setSubject] = useState("");
  const [description, setDescription] = useState("");
  const [customerQuery, setCustomerQuery] = useState("");
  const [customer, setCustomer] = useState<CustomerSearchResult | null>(null);
  const [organizationId, setOrganizationId] = useState<number | "">("");
  const [submitted, setSubmitted] = useState(false);

  const customerMissing = mode === "existing" && !customer;
  const organizationMissing = mode === "unclaimed" && organizationId === "";

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
    if (!subject.trim() || !description.trim() || customerMissing || organizationMissing) return;
    create.mutate(
      {
        subject: subject.trim(),
        description: description.trim(),
        ...(mode === "existing" ? { requester_id: customer!.id } : { organization_id: organizationId as number }),
      },
      { onSuccess: (ticket) => navigate(`/agent/tickets/${ticket.id}`) },
    );
  }

  return (
    <Box sx={{ p: { xs: 2, md: 3 }, maxWidth: 640 }}>
      <Typography variant="titleLarge" component="h1" sx={{ mb: 0.5 }}>
        New ticket
      </Typography>
      <Typography variant="bodyMedium" sx={{ mb: 3, color: sys("onSurfaceVariant") }}>
        For a customer who called or emailed you directly.
      </Typography>

      <Box component="form" onSubmit={onSubmit} noValidate>
        <Stack spacing={3}>
          {create.isError ? (
            <Alert severity="error" variant="filled" sx={{ bgcolor: sys("errorContainer"), color: sys("onErrorContainer") }}>
              {errorMessage(create.error, "That ticket couldn't be created.")}
            </Alert>
          ) : null}

          <Box>
            <Typography variant="labelLarge" sx={{ display: "block", mb: 1, color: sys("onSurfaceVariant") }}>
              Who's this for?
            </Typography>
            <ToggleButtonGroup
              exclusive
              size="small"
              value={mode}
              onChange={(_, v: Mode | null) => v && setMode(v)}
              aria-label="Who this ticket is for"
            >
              <ToggleButton value="existing">Existing customer</ToggleButton>
              <ToggleButton value="unclaimed">No account yet</ToggleButton>
            </ToggleButtonGroup>
          </Box>

          {mode === "existing" ? (
            <CustomerPicker
              label="Customer"
              required
              value={customer}
              onChange={setCustomer}
              query={customerQuery}
              onQueryChange={setCustomerQuery}
              error={submitted && customerMissing}
              helperText={submitted && customerMissing ? "Search and pick the customer" : "Search by name or email"}
            />
          ) : (
            <TextField
              select
              label="Organisation"
              required
              fullWidth
              value={organizationId}
              onChange={(e) => setOrganizationId(e.target.value === "" ? "" : Number(e.target.value))}
              error={submitted && organizationMissing}
              helperText={
                submitted && organizationMissing
                  ? "Pick the organisation this is for"
                  : "Once this customer registers, an agent can link this ticket to their account."
              }
            >
              {(organizations.data ?? [])
                .filter((o) => o.active)
                .map((o) => (
                  <MenuItem key={o.id} value={o.id}>
                    {o.name}
                  </MenuItem>
                ))}
            </TextField>
          )}

          <TextField
            label="Subject"
            value={subject}
            onChange={(e) => setSubject(e.target.value)}
            required
            fullWidth
            slotProps={{ htmlInput: { maxLength: 255 } }}
            error={submitted && !subject.trim()}
            helperText={submitted && !subject.trim() ? "Add a short subject" : undefined}
          />
          <TextField
            label="Details"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            required
            fullWidth
            multiline
            minRows={6}
            error={submitted && !description.trim()}
            helperText={submitted && !description.trim() ? "Describe what the customer told you" : undefined}
          />

          <Stack direction="row" spacing={1}>
            <Button type="submit" variant="contained" size="large" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create ticket"}
            </Button>
            <Button component={RouterLink} to="/agent" size="large">
              Cancel
            </Button>
          </Stack>
        </Stack>
      </Box>
    </Box>
  );
}
