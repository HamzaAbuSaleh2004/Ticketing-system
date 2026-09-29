import { Autocomplete, Box, TextField, Typography } from "@mui/material";
import { MIN_QUERY, useCustomerSearch } from "../api/hooks";
import type { CustomerSearchResult } from "../api/types";
import { sys } from "../theme/scheme";

/** A search-as-you-type picker over existing end_user accounts: creating or
 * claiming a ticket on behalf of a customer both search the same way. */
export function CustomerPicker({
  value,
  onChange,
  query,
  onQueryChange,
  label,
  size,
  required,
  error,
  helperText,
}: {
  value: CustomerSearchResult | null;
  onChange: (v: CustomerSearchResult | null) => void;
  query: string;
  onQueryChange: (q: string) => void;
  label: string;
  size?: "small" | "medium";
  required?: boolean;
  error?: boolean;
  helperText?: string;
}) {
  const search = useCustomerSearch(query);
  return (
    <Autocomplete
      size={size}
      options={search.data ?? []}
      value={value}
      onChange={(_, v) => onChange(v)}
      inputValue={query}
      onInputChange={(_, v) => onQueryChange(v)}
      getOptionLabel={(o) => `${o.name} (${o.email})`}
      isOptionEqualToValue={(a, b) => a.id === b.id}
      loading={search.isFetching}
      noOptionsText={query.trim().length < MIN_QUERY ? "Keep typing a name or email…" : "No customer matches"}
      renderOption={({ key, ...optionProps }, option) => (
        <Box component="li" key={option.id} {...optionProps}>
          <Box>
            <Typography component="span" variant="bodyMedium" sx={{ display: "block" }}>
              {option.name}
            </Typography>
            <Typography component="span" variant="bodySmall" sx={{ display: "block", color: sys("onSurfaceVariant") }}>
              {option.email}
            </Typography>
            {option.organization_name ? (
              <Typography component="span" variant="bodySmall" sx={{ display: "block", color: sys("onSurfaceVariant") }}>
                {option.organization_name}
              </Typography>
            ) : null}
          </Box>
        </Box>
      )}
      renderInput={(params) => <TextField {...params} label={label} required={required} error={error} helperText={helperText} />}
    />
  );
}
