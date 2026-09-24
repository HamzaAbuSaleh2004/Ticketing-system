import ArrowDropDown from "@mui/icons-material/ArrowDropDown";
import Check from "@mui/icons-material/Check";
import { ButtonBase, ListItemIcon, ListItemText, Menu, MenuItem } from "@mui/material";
import { useState } from "react";
import { sys } from "../../theme/scheme";
import { typescale } from "../../theme/tokens";

export type FilterOption = { value: string | null; label: string };

/** M3 filter chip with a menu. Selected (anything but the default) uses
 * secondary-container plus a check, so the state isn't colour alone. */
export function FilterChip({
  label,
  value,
  options,
  onChange,
  defaultValue = null,
}: {
  label: string;
  value: string | null;
  options: FilterOption[];
  onChange: (value: string | null) => void;
  defaultValue?: string | null;
}) {
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const selected = value !== defaultValue;
  const current = options.find((o) => o.value === value)?.label ?? label;

  return (
    <>
      <ButtonBase
        onClick={(e) => setAnchor(e.currentTarget)}
        aria-haspopup="menu"
        aria-expanded={anchor !== null}
        aria-label={`${label}: ${current}`}
        sx={{
          position: "relative",
          height: 32,
          pl: selected ? 1 : 1.5,
          pr: 0.5,
          gap: 0.5,
          borderRadius: "var(--md-sys-shape-corner-full)",
          border: selected ? "none" : `1px solid ${sys("outline")}`,
          bgcolor: selected ? sys("secondaryContainer") : "transparent",
          color: selected ? sys("onSecondaryContainer") : sys("onSurfaceVariant"),
          ...typescale("label-large"),
          "&:hover": { bgcolor: selected ? sys("secondaryContainer") : sys("surfaceContainerHigh") },
          "&:focus-visible": { outline: `2px solid ${sys("primary")}`, outlineOffset: 2 },
          // 48dp touch target around the 32dp chip.
          "&::after": { content: '""', position: "absolute", inset: "-8px 0" },
        }}
      >
        {selected ? <Check sx={{ fontSize: 18 }} /> : null}
        {selected ? current : label}
        <ArrowDropDown sx={{ fontSize: 20 }} />
      </ButtonBase>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}>
        {options.map((o) => (
          <MenuItem
            key={o.value ?? "__all"}
            selected={o.value === value}
            role="menuitemradio"
            aria-checked={o.value === value}
            dense
            onClick={() => {
              onChange(o.value);
              setAnchor(null);
            }}
          >
            <ListItemIcon>{o.value === value ? <Check fontSize="small" /> : null}</ListItemIcon>
            <ListItemText>{o.label}</ListItemText>
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}
