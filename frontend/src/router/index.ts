import { createRouter, createWebHistory } from "vue-router";
import type { RouteLocationNormalized } from "vue-router";

import { homeRouteForRole, useAuth } from "../composables/useAuth";
import AuthView from "../views/auth/AuthView.vue";
import LandingView from "../views/public/LandingView.vue";
import AdminCompaniesView from "../views/admin/AdminCompaniesView.vue";
import AdminConnectorsView from "../views/admin/AdminConnectorsView.vue";
import AdminDashboardView from "../views/admin/AdminDashboardView.vue";
import AdminJobsView from "../views/admin/AdminJobsView.vue";
import AdminLayout from "../views/admin/AdminLayout.vue";
import AdminLogsView from "../views/admin/AdminLogsView.vue";
import AdminNotificationsView from "../views/admin/AdminNotificationsView.vue";
import AdminRequestsView from "../views/admin/AdminRequestsView.vue";
import AdminSettingsView from "../views/admin/AdminSettingsView.vue";
import AdminUsersView from "../views/admin/AdminUsersView.vue";
import AdminWatchlistsView from "../views/admin/AdminWatchlistsView.vue";
import UserCompaniesView from "../views/user/UserCompaniesView.vue";
import UserDashboardView from "../views/user/UserDashboardView.vue";
import UserJobsView from "../views/user/UserJobsView.vue";
import UserLayout from "../views/user/UserLayout.vue";
import UserNotificationsView from "../views/user/UserNotificationsView.vue";
import UserPreferencesView from "../views/user/UserPreferencesView.vue";
import UserProfileView from "../views/user/UserProfileView.vue";
import UserResumesView from "../views/user/UserResumesView.vue";
import UserWatchlistsView from "../views/user/UserWatchlistsView.vue";

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior() {
    return { top: 0 };
  },
  routes: [
    { path: "/", name: "landing", component: LandingView, meta: { title: "Never miss a job" } },
    { path: "/auth", redirect: "/auth/login" },
    {
      path: "/auth/login",
      name: "login",
      component: AuthView,
      props: { mode: "login", audience: "user" },
      meta: { guestOnly: true, title: "Login" },
    },
    {
      path: "/auth/signup",
      name: "signup",
      component: AuthView,
      props: { mode: "signup", audience: "user" },
      meta: { guestOnly: true, title: "Create account" },
    },
    {
      path: "/auth/forgot-password",
      name: "forgot-password",
      component: AuthView,
      props: { mode: "forgot", audience: "user" },
      meta: { guestOnly: true, title: "Forgot password" },
    },
    {
      path: "/admin/login",
      name: "admin-login",
      component: AuthView,
      props: { mode: "login", audience: "admin" },
      meta: { guestOnly: true, title: "Admin login" },
    },
    {
      path: "/user",
      component: UserLayout,
      meta: { requiresAuth: true, requiresUser: true, title: "User Workspace" },
      children: [
        { path: "", redirect: "/user/dashboard" },
        { path: "dashboard", component: UserDashboardView, meta: { requiresAuth: true, requiresUser: true, title: "Dashboard" } },
        { path: "jobs", component: UserJobsView, meta: { requiresAuth: true, requiresUser: true, title: "Jobs", headerSearch: false } },
        { path: "notifications", component: UserNotificationsView, meta: { requiresAuth: true, requiresUser: true, title: "Notifications" } },
        { path: "resumes", component: UserResumesView, meta: { requiresAuth: true, requiresUser: true, title: "Resumes" } },
        { path: "companies", component: UserCompaniesView, meta: { requiresAuth: true, requiresUser: true, title: "Companies" } },
        { path: "watchlists", component: UserWatchlistsView, meta: { requiresAuth: true, requiresUser: true, title: "Watchlists" } },
        { path: "preferences", component: UserPreferencesView, meta: { requiresAuth: true, requiresUser: true, title: "Preferences" } },
        { path: "profile", component: UserProfileView, meta: { requiresAuth: true, requiresUser: true, title: "Profile" } },
      ],
    },
    {
      path: "/admin",
      component: AdminLayout,
      meta: { requiresAuth: true, requiresAdmin: true, title: "Admin Console" },
      children: [
        { path: "", redirect: "/admin/dashboard" },
        { path: "dashboard", component: AdminDashboardView, meta: { requiresAuth: true, requiresAdmin: true, title: "Dashboard" } },
        { path: "users", component: AdminUsersView, meta: { requiresAuth: true, requiresAdmin: true, title: "Users" } },
        { path: "companies", component: AdminCompaniesView, meta: { requiresAuth: true, requiresAdmin: true, title: "Companies" } },
        { path: "requests", component: AdminRequestsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Requests" } },
        { path: "connectors", component: AdminConnectorsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Connectors" } },
        { path: "jobs", component: AdminJobsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Jobs" } },
        { path: "notifications", component: AdminNotificationsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Notifications" } },
        { path: "watchlists", component: AdminWatchlistsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Watchlists" } },
        { path: "logs", component: AdminLogsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Logs" } },
        { path: "settings", component: AdminSettingsView, meta: { requiresAuth: true, requiresAdmin: true, title: "Settings" } },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

function isAdminPath(route: RouteLocationNormalized): boolean {
  return route.path === "/admin" || route.path.startsWith("/admin/");
}

function redirectForUnauthorized(route: RouteLocationNormalized): string | undefined {
  const auth = useAuth();
  const currentUser = auth.user.value;

  if (route.meta.requiresAuth && !currentUser) {
    return isAdminPath(route) ? "/admin/login" : "/auth/login";
  }
  if (route.meta.requiresAdmin && currentUser?.role === "user") {
    return homeRouteForRole(currentUser.role);
  }
  if (route.meta.requiresUser && currentUser && currentUser.role !== "user") {
    return homeRouteForRole(currentUser.role);
  }
  if (route.meta.guestOnly && currentUser) {
    return homeRouteForRole(currentUser.role);
  }
  return undefined;
}

router.beforeEach(async (to) => {
  const auth = useAuth();
  await auth.init();
  const redirect = redirectForUnauthorized(to);
  if (redirect) {
    return redirect;
  }
  document.title = typeof to.meta.title === "string" ? `${to.meta.title} | TryApplyPilot` : "TryApplyPilot";
  return true;
});

export default router;
