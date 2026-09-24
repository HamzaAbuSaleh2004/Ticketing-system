import LogoutOutlined from "@mui/icons-material/LogoutOutlined";
import { Avatar, Box, Divider, IconButton, ListItemIcon, Menu, MenuItem, Tooltip, Typography } from "@mui/material";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { sys } from "../theme/scheme";

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export function AccountMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [anchor, setAnchor] = useState<HTMLElement | null>(null);
  if (!user) return null;

  return (
    <>
      <Tooltip title="Account">
        <IconButton aria-label={`Account: ${user.name}`} onClick={(e) => setAnchor(e.currentTarget)} sx={{ width: 48, height: 48 }}>
          <Avatar
            sx={{
              width: 32,
              height: 32,
              bgcolor: sys("tertiaryContainer"),
              color: sys("onTertiaryContainer"),
              fontSize: "var(--md-sys-typescale-label-large-size)",
              fontWeight: 500,
            }}
          >
            {initials(user.name)}
          </Avatar>
        </IconButton>
      </Tooltip>
      <Menu anchorEl={anchor} open={anchor !== null} onClose={() => setAnchor(null)}>
        <Box sx={{ px: 2, py: 1, minWidth: 220 }}>
          <Typography variant="titleSmall">{user.name}</Typography>
          <Typography variant="bodySmall" sx={{ color: sys("onSurfaceVariant") }}>
            {user.email}
          </Typography>
        </Box>
        <Divider />
        <MenuItem
          onClick={() => {
            setAnchor(null);
            logout();
            navigate("/login", { replace: true });
          }}
        >
          <ListItemIcon>
            <LogoutOutlined fontSize="small" />
          </ListItemIcon>
          Sign out
        </MenuItem>
      </Menu>
    </>
  );
}
