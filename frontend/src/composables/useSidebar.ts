import { computed, ref } from "vue";

const COLLAPSED_KEY = "tryapplypilot-sidebar-collapsed";
const PINNED_KEY = "tryapplypilot-sidebar-pinned";

const isDesktop = ref(true);
const collapsed = ref(true);
const pinned = ref(false);
const hovered = ref(false);
const mobileOpen = ref(false);
let initialized = false;
let media: MediaQueryList | null = null;

function syncViewport(): void {
  isDesktop.value = media?.matches ?? true;
  if (isDesktop.value) {
    mobileOpen.value = false;
  }
}

function persistState(): void {
  window.localStorage.setItem(COLLAPSED_KEY, collapsed.value ? "1" : "0");
  window.localStorage.setItem(PINNED_KEY, pinned.value ? "1" : "0");
}

export function useSidebar() {
  function init(): void {
    if (initialized) {
      return;
    }
    initialized = true;
    media = window.matchMedia("(min-width: 1024px)");
    collapsed.value = window.localStorage.getItem(COLLAPSED_KEY) !== "0";
    pinned.value = window.localStorage.getItem(PINNED_KEY) === "1";
    syncViewport();
    media.addEventListener("change", syncViewport);
  }

  function setHovered(value: boolean): void {
    if (!isDesktop.value || pinned.value) {
      hovered.value = false;
      return;
    }
    hovered.value = value;
  }

  function togglePin(): void {
    pinned.value = !pinned.value;
    collapsed.value = !pinned.value;
    persistState();
  }

  function toggleDesktop(): void {
    if (!isDesktop.value) {
      mobileOpen.value = !mobileOpen.value;
      return;
    }
    if (pinned.value || !collapsed.value) {
      pinned.value = false;
      collapsed.value = true;
    } else {
      collapsed.value = false;
      pinned.value = true;
    }
    persistState();
  }

  function openMobile(): void {
    mobileOpen.value = true;
  }

  function closeMobile(): void {
    mobileOpen.value = false;
  }

  function closeAfterNavigation(): void {
    if (!isDesktop.value) {
      mobileOpen.value = false;
    }
  }

  return {
    isDesktop,
    collapsed,
    pinned,
    hovered,
    mobileOpen,
    expanded: computed(() => isDesktop.value && (!collapsed.value || pinned.value || hovered.value)),
    init,
    togglePin,
    toggleDesktop,
    openMobile,
    closeMobile,
    closeAfterNavigation,
    setHovered,
  };
}
