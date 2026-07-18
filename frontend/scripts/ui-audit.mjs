import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const frontendRoot = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");

const auditedRoutes = [
  {
    label: "Auth",
    paths: ["/auth/login", "/auth/signup", "/auth/forgot-password"],
    file: "src/views/auth/AuthView.vue",
  },
  { label: "Dashboard", paths: ["/user/dashboard"], file: "src/views/user/UserDashboardView.vue" },
  { label: "Jobs", paths: ["/user/jobs"], file: "src/views/user/UserJobsView.vue" },
  { label: "Preferences", paths: ["/user/preferences"], file: "src/views/user/UserPreferencesView.vue" },
  { label: "Profile", paths: ["/user/profile"], file: "src/views/user/UserProfileView.vue" },
  { label: "Resumes", paths: ["/user/resumes"], file: "src/views/user/UserResumesView.vue" },
  { label: "Companies", paths: ["/user/companies"], file: "src/views/user/UserCompaniesView.vue" },
  { label: "Watchlists", paths: ["/user/watchlists"], file: "src/views/user/UserWatchlistsView.vue" },
  { label: "Admin Dashboard", paths: ["/admin/dashboard"], file: "src/views/admin/AdminDashboardView.vue" },
  { label: "Admin Users", paths: ["/admin/users"], file: "src/views/admin/AdminUsersView.vue" },
  { label: "Admin Jobs", paths: ["/admin/jobs"], file: "src/views/admin/AdminJobsView.vue" },
  { label: "Admin Settings", paths: ["/admin/settings"], file: "src/views/admin/AdminSettingsView.vue" },
  { label: "Admin Companies", paths: ["/admin/companies"], file: "src/views/admin/AdminCompaniesView.vue" },
  { label: "Admin Connectors", paths: ["/admin/connectors"], file: "src/views/admin/AdminConnectorsView.vue" },
];

const primitiveChecks = [
  {
    label: "Spacing tokens",
    file: "src/styles/tokens.css",
    expectations: [
      "--space-1: 4px;",
      "--space-2: 8px;",
      "--space-3: 12px;",
      "--space-4: 16px;",
      "--space-5: 20px;",
      "--space-6: 24px;",
      "--space-7: 32px;",
      "--space-8: 40px;",
    ],
  },
  {
    label: "PageSection",
    file: "src/components/layout/PageSection.vue",
    expectations: ['class="page-section"'],
  },
  {
    label: "AppCard",
    file: "src/components/ui/AppCard.vue",
    expectations: ["app-card__body", "card-content"],
  },
  {
    label: "Responsive grid gaps",
    file: "src/styles/layout.css",
    expectations: ["--grid-gap-desktop", "--grid-gap-tablet", "--grid-gap-mobile", ".app-grid"],
  },
  {
    label: "Form field spacing",
    file: "src/styles/layout.css",
    expectations: [".app-form-grid", ".app-checkbox-group"],
  },
];

const STOP_RECURSION_SEGMENTS = ["src/components/ui/", "src/components/layout/"];

function readFile(relativePath) {
  return fs.readFileSync(path.join(frontendRoot, relativePath), "utf8");
}

function fileExists(relativePath) {
  return fs.existsSync(path.join(frontendRoot, relativePath));
}

function normalizePath(relativePath) {
  return relativePath.split(path.sep).join("/");
}

function resolveVueImport(baseFile, specifier) {
  const baseDir = path.dirname(path.join(frontendRoot, baseFile));
  const candidates = [specifier, `${specifier}.vue`, path.join(specifier, "index.vue")];

  for (const candidate of candidates) {
    const absolute = path.resolve(baseDir, candidate);
    if (fs.existsSync(absolute) && absolute.endsWith(".vue")) {
      return normalizePath(path.relative(frontendRoot, absolute));
    }
  }

  return null;
}

function getVueImports(relativePath) {
  const content = readFile(relativePath);
  const imports = [];

  for (const match of content.matchAll(/import\s+[\s\S]*?\s+from\s+["'](\.{1,2}\/[^"']+)["']/g)) {
    const resolved = resolveVueImport(relativePath, match[1]);
    if (resolved) {
      imports.push(resolved);
    }
  }

  return imports;
}

function collectRouteTree(entryFile, seen = new Set()) {
  if (seen.has(entryFile)) {
    return [];
  }

  seen.add(entryFile);
  const files = [entryFile];

  for (const importedFile of getVueImports(entryFile)) {
    if (STOP_RECURSION_SEGMENTS.some((segment) => importedFile.includes(segment))) {
      continue;
    }
    files.push(...collectRouteTree(importedFile, seen));
  }

  return files;
}

function extractStyleBlocks(content) {
  const blocks = [];
  for (const match of content.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)) {
    blocks.push(match[1]);
  }
  return blocks;
}

function isAllowedSpacingValue(value) {
  const normalized = value.replace(/\s+/g, " ").trim();

  if (
    /^(0|auto|inherit|initial|unset|revert)(\s+(0|auto|inherit|initial|unset|revert)){0,3}$/u.test(normalized) ||
    normalized.includes("var(") ||
    normalized.includes("calc(")
  ) {
    return true;
  }

  return false;
}

function findHardcodedSpacing(relativePath) {
  const issues = [];
  const content = readFile(relativePath);

  for (const block of extractStyleBlocks(content)) {
    for (const match of block.matchAll(/\b(padding(?:-[a-z]+)?|margin(?:-[a-z]+)?|gap)\s*:\s*([^;]+);/g)) {
      const [, property, value] = match;
      if (!isAllowedSpacingValue(value)) {
        issues.push(`${relativePath}: ${property}: ${value.trim()}`);
      }
    }
  }

  return issues;
}

function usesTag(relativePath, tagName) {
  return new RegExp(`<${tagName}\\b`, "u").test(readFile(relativePath));
}

function routeUsesAppCard(files) {
  return files.some((file) => usesTag(file, "AppCard"));
}

function routeEscapesCardPrimitive(files) {
  return files
    .filter((file) => /surface-card/u.test(readFile(file)))
    .map((file) => `${file}: uses surface-card directly`);
}

function runPrimitiveAudit() {
  return primitiveChecks.map((check) => {
    const content = readFile(check.file);
    const missing = check.expectations.filter((expectation) => !content.includes(expectation));
    return {
      ...check,
      passed: missing.length === 0,
      missing,
    };
  });
}

function runRouteAudit(route) {
  const files = collectRouteTree(route.file);
  const issues = [];

  if (!usesTag(route.file, "PageSection")) {
    issues.push("Missing PageSection");
  }

  if (!usesTag(route.file, "AppGrid")) {
    issues.push("Missing AppGrid");
  }

  if (!routeUsesAppCard(files)) {
    issues.push("Missing AppCard in route component tree");
  }

  const hardcodedSpacing = files.flatMap((file) => findHardcodedSpacing(file));
  if (hardcodedSpacing.length > 0) {
    for (const issue of hardcodedSpacing) {
      issues.push(`Hardcoded spacing: ${issue}`);
    }
  }

  for (const escape of routeEscapesCardPrimitive(files)) {
    issues.push(`Card primitive escape: ${escape}`);
  }

  return {
    ...route,
    passed: issues.length === 0,
    issues,
  };
}

function printLine(line = "") {
  process.stdout.write(`${line}\n`);
}

function main() {
  const primitiveResults = runPrimitiveAudit();
  const routeResults = auditedRoutes.map(runRouteAudit);
  const hasFailures = primitiveResults.some((result) => !result.passed) || routeResults.some((result) => !result.passed);

  printLine("UI Audit");
  printLine("Primitives");

  for (const result of primitiveResults) {
    if (result.passed) {
      printLine(`✓ ${result.label}`);
      continue;
    }

    printLine(`✗ ${result.label}`);
    for (const missing of result.missing) {
      printLine(`  Missing: ${missing}`);
    }
  }

  printLine("Routes");

  for (const result of routeResults) {
    const pathLabel = result.paths.join(", ");
    if (result.passed) {
      printLine(`✓ ${result.label} (${pathLabel})`);
      continue;
    }

    printLine(`✗ ${result.label} (${pathLabel})`);
    for (const issue of result.issues) {
      printLine(`  ${issue}`);
    }
  }

  printLine("Static checks: AppCard usage in the route component tree, PageSection/AppGrid adoption, tokenized spacing declarations, and direct card-primitive escapes.");

  if (hasFailures) {
    process.exitCode = 1;
  }
}

main();
