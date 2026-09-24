export type Role = "end_user" | "agent" | "admin";
export type Team = "tier1" | "senior";

export type User = {
  id: number;
  email: string;
  name: string;
  role: Role;
  team: Team | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: User;
};
