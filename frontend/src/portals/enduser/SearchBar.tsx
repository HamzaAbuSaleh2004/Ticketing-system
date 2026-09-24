import CloseOutlined from "@mui/icons-material/CloseOutlined";
import SearchOutlined from "@mui/icons-material/SearchOutlined";
import { Box, IconButton, InputBase } from "@mui/material";
import { useEffect, useState, type FormEvent } from "react";
import { sys } from "../../theme/scheme";
import { typescale } from "../../theme/tokens";

/** M3 search bar: full-shape, surface-container-high, 56dp. Searches on
 * Enter rather than per keystroke, so each Gemini call is intentional. */
export function SearchBar({ value, onSearch }: { value: string; onSearch: (q: string) => void }) {
  const [draft, setDraft] = useState(value);
  useEffect(() => {
    setDraft(value);
  }, [value]);

  function submit(e: FormEvent) {
    e.preventDefault();
    onSearch(draft.trim());
  }

  return (
    <Box
      component="form"
      role="search"
      onSubmit={submit}
      sx={{
        display: "flex",
        alignItems: "center",
        gap: 0.5,
        height: 56,
        pl: 2,
        pr: 0.5,
        borderRadius: "var(--md-sys-shape-corner-full)",
        bgcolor: sys("surfaceContainerHigh"),
        color: sys("onSurface"),
        "&:focus-within": { outline: `2px solid ${sys("primary")}`, outlineOffset: 0 },
      }}
    >
      <SearchOutlined sx={{ color: sys("onSurfaceVariant") }} />
      <InputBase
        type="search"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        placeholder="Describe your problem, like “I forgot my password”"
        inputProps={{ "aria-label": "Search help articles", enterKeyHint: "search", maxLength: 500 }}
        sx={{ flex: 1, alignSelf: "stretch", ml: 1, ...typescale("body-large"), "& input": { height: "100%", py: 0 }, "& input::placeholder": { color: sys("onSurfaceVariant"), opacity: 1 },
          // Our own clear button replaces the browser's.
          "& input::-webkit-search-cancel-button": { display: "none" },
        }}
      />
      {draft ? (
        <IconButton
          aria-label="Clear search"
          onClick={() => {
            setDraft("");
            onSearch("");
          }}
          sx={{ width: 48, height: 48 }}
        >
          <CloseOutlined />
        </IconButton>
      ) : null}
    </Box>
  );
}
