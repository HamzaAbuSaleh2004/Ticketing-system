import { Typography } from "@mui/material";
import type { ReactNode } from "react";
import { sys } from "../theme/scheme";

/** A small caption above a group of fields, so a panel reads as labeled
 * properties (or a ticket's own facts vs. its conversation) rather than one
 * undifferentiated block. */
export function SectionCaption({ children }: { children: ReactNode }) {
  return (
    <Typography variant="labelMedium" component="h2" sx={{ color: sys("onSurfaceVariant") }}>
      {children}
    </Typography>
  );
}
