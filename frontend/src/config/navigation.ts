import type { SidebarItem } from "../types";

export const userNavigation: SidebarItem[] = [
  { label: "Dashboard", to: "/user/dashboard", icon: "LayoutDashboard" },
  { label: "Jobs", to: "/user/jobs", icon: "BriefcaseBusiness" },
  { label: "Notifications", to: "/user/notifications", icon: "Bell" },
  { label: "Resumes", to: "/user/resumes", icon: "FileText" },
  { label: "Companies", to: "/user/companies", icon: "Building2" },
  { label: "Watchlists", to: "/user/watchlists", icon: "Star" },
  { label: "Preferences", to: "/user/preferences", icon: "SlidersHorizontal" },
  { label: "Profile", to: "/user/profile", icon: "UserRound" },
];

export const adminNavigation: SidebarItem[] = [
  { label: "Dashboard", to: "/admin/dashboard", icon: "LayoutDashboard" },
  { label: "Users", to: "/admin/users", icon: "Users" },
  { label: "Companies", to: "/admin/companies", icon: "Building2" },
  { label: "Requests", to: "/admin/requests", icon: "ScrollText" },
  { label: "Connectors", to: "/admin/connectors", icon: "Cable" },
  { label: "Jobs", to: "/admin/jobs", icon: "BriefcaseBusiness" },
  { label: "Notifications", to: "/admin/notifications", icon: "Bell" },
  { label: "Watchlists", to: "/admin/watchlists", icon: "Star" },
  { label: "Logs", to: "/admin/logs", icon: "FileText" },
  { label: "Settings", to: "/admin/settings", icon: "Settings" },
];
