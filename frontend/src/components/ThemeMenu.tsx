import Check from "@mui/icons-material/Check";
import ContrastOutlined from "@mui/icons-material/ContrastOutlined";
import { IconButton, ListItemIcon, ListItemText, ListSubheader, Menu, MenuItem, Tooltip } from "@mui/material";
import { useState } from "react";
import type { Contrast } from "../theme/scheme";
import { useThemeController } from "../theme/ThemeController";

const CONTRASTS: { value: Contrast; label: string }[] = [
  { value: 0, label: "Standard contrast" },
  { value: 0.5, label: "Medium contrast" },
  { value: 1, label: "High contrast" },
];

export function ThemeMenu() {
  const { contrast, setContrast } = useThemeController();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);

  const item = (selected: boolean, label: string, onClick: () => void) => (
    <MenuItem
      key={label}
      selected={selected}
      onClick={() => {
        onClick();
        setAnchor(null);
      }}
      role="menuitemradio"
      aria-checked={selected}
    >
      <ListItemIcon>{selected ? <Check fontSize="small" /> : null}</ListItemIcon>
      <ListItemText>{label}</ListItemText>
    </MenuItem>
  );

  return (
    <>
      <Tooltip title="Contrast">
        <IconButton aria-label="Contrast" onClick={(e) => setAnchor(e.currentTarget)} sx={{ width: 48, height: 48 }}>
          <ContrastOutlined />
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}>
        <ListSubheader sx={{ bgcolor: "transparent", lineHeight: "36px" }}>Contrast</ListSubheader>
        {CONTRASTS.map((c) => item(contrast === c.value, c.label, () => setContrast(c.value)))}
      </Menu>
    </>
  );
}
