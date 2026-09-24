import BrightnessAutoOutlined from "@mui/icons-material/BrightnessAutoOutlined";
import Check from "@mui/icons-material/Check";
import DarkModeOutlined from "@mui/icons-material/DarkModeOutlined";
import LightModeOutlined from "@mui/icons-material/LightModeOutlined";
import { Divider, IconButton, ListItemIcon, ListItemText, ListSubheader, Menu, MenuItem, Tooltip } from "@mui/material";
import { useState } from "react";
import type { Contrast } from "../theme/scheme";
import { useThemeController, type ThemeMode } from "../theme/ThemeController";

const MODES: { value: ThemeMode; label: string }[] = [
  { value: "system", label: "Match system" },
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
];

const CONTRASTS: { value: Contrast; label: string }[] = [
  { value: 0, label: "Standard contrast" },
  { value: 0.5, label: "Medium contrast" },
  { value: 1, label: "High contrast" },
];

export function ThemeMenu() {
  const { mode, setMode, contrast, setContrast } = useThemeController();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  const Icon = mode === "light" ? LightModeOutlined : mode === "dark" ? DarkModeOutlined : BrightnessAutoOutlined;

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
      <Tooltip title="Appearance">
        <IconButton aria-label="Appearance" onClick={(e) => setAnchor(e.currentTarget)} sx={{ width: 48, height: 48 }}>
          <Icon />
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}>
        <ListSubheader sx={{ bgcolor: "transparent", lineHeight: "36px" }}>Theme</ListSubheader>
        {MODES.map((m) => item(mode === m.value, m.label, () => setMode(m.value)))}
        <Divider />
        <ListSubheader sx={{ bgcolor: "transparent", lineHeight: "36px" }}>Contrast</ListSubheader>
        {CONTRASTS.map((c) => item(contrast === c.value, c.label, () => setContrast(c.value)))}
      </Menu>
    </>
  );
}
