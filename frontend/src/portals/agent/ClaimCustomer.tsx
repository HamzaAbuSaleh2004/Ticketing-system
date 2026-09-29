import { Button, Stack, Typography } from "@mui/material";
import { useState } from "react";
import { errorMessage } from "../../api/client";
import { usePatchTicket } from "../../api/hooks";
import type { CustomerSearchResult } from "../../api/types";
import { CustomerPicker } from "../../components/CustomerPicker";
import { sys } from "../../theme/scheme";

/** An unclaimed ticket (staff-created for a customer with no account yet)
 * has no requester. Once that customer registers, an agent finds and links
 * their account here, and the ticket then shows up for them too. */
export function ClaimCustomer({ ticketId, onError }: { ticketId: number; onError: (message: string) => void }) {
  const patch = usePatchTicket(ticketId);
  const [query, setQuery] = useState("");
  const [customer, setCustomer] = useState<CustomerSearchResult | null>(null);

  return (
    <Stack spacing={0.75}>
      <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
        No customer linked yet.
      </Typography>
      <Stack direction="row" sx={{ gap: 1, alignItems: "flex-start", maxWidth: 420 }}>
        <CustomerPicker
          size="small"
          label="Link a customer"
          value={customer}
          onChange={setCustomer}
          query={query}
          onQueryChange={setQuery}
        />
        <Button
          size="small"
          disabled={!customer || patch.isPending}
          onClick={() =>
            customer &&
            patch.mutate(
              { requester_id: customer.id },
              {
                onSuccess: () => setCustomer(null),
                onError: (e) => onError(errorMessage(e, "That didn't link. Try again.")),
              },
            )
          }
          sx={{ mt: 0.5, flexShrink: 0 }}
        >
          Link
        </Button>
      </Stack>
    </Stack>
  );
}
