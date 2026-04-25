#!/usr/bin/env node

const fs = require("fs");
const os = require("os");
const path = require("path");
const { spawnSync } = require("child_process");

const packageRoot = path.resolve(__dirname, "..");
const metadata = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));
const packageVersion = String(metadata.version || "").trim();
const melissaHome = process.env.MELISSA_HOME || path.join(os.homedir(), ".melissa");
const repoDir = path.join(melissaHome, "repo");
const runtimeDir = path.join(melissaHome, "runtime");
const entrypoint = path.join(repoDir, "melissa_cli.py");

const SKIP_NAMES = new Set([
  ".git",
  ".github",
  ".nova",
  ".pytest_cache",
  ".ruff_cache",
  ".venv",
  "__pycache__",
  "backups",
  "docs",
  "logs",
  "node_modules",
  "output",
  "screenshots",
  "tests",
  "tmp",
]);

function ensureDir(target) {
  fs.mkdirSync(target, { recursive: true });
}

function status(message) {
  console.error(`[melissa] ${message}`);
}

function fail(message) {
  console.error(`ERR ${message}`);
  process.exit(1);
}

function runtimeCandidates() {
  return [
    path.join(runtimeDir, "bin", "python"),
    path.join(runtimeDir, "bin", "python3"),
    path.join(runtimeDir, "Scripts", "python.exe"),
  ];
}

function resolveRuntime() {
  for (const candidate of runtimeCandidates()) {
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }
  return "";
}

function runAndReturn(command, args, extraEnv = {}, options = {}) {
  return spawnSync(command, args, {
    stdio: "inherit",
    env: { ...process.env, ...extraEnv },
    ...options,
  });
}

function syncTree(sourceDir, targetDir) {
  ensureDir(targetDir);
  for (const entry of fs.readdirSync(sourceDir, { withFileTypes: true })) {
    if (SKIP_NAMES.has(entry.name)) {
      continue;
    }
    const sourcePath = path.join(sourceDir, entry.name);
    const targetPath = path.join(targetDir, entry.name);
    if (entry.isDirectory()) {
      syncTree(sourcePath, targetPath);
      continue;
    }
    ensureDir(path.dirname(targetPath));
    fs.copyFileSync(sourcePath, targetPath);
  }
}

function readInstalledVersion() {
  const installedPackage = path.join(repoDir, "package.json");
  if (!fs.existsSync(installedPackage)) {
    return "";
  }
  try {
    const payload = JSON.parse(fs.readFileSync(installedPackage, "utf8"));
    return String(payload.version || "").trim();
  } catch (_err) {
    return "";
  }
}

function findSystemPython() {
  const candidates =
    process.platform === "win32"
      ? [
          ["py", ["-3"]],
          ["python", []],
          ["python3", []],
        ]
      : [
          ["python3", []],
          ["python", []],
        ];
  for (const [command, prefixArgs] of candidates) {
    const probe = spawnSync(command, [...prefixArgs, "-c", "import sys; print(sys.executable)"], {
      stdio: ["ignore", "pipe", "pipe"],
      encoding: "utf8",
      env: process.env,
    });
    if (probe.status === 0) {
      return { command, prefixArgs };
    }
  }
  return null;
}

function ensureRuntime() {
  let runtime = resolveRuntime();
  if (runtime) {
    return runtime;
  }
  status("Preparando runtime aislado de Melissa. El primer arranque puede tardar 30-90s.");
  ensureDir(melissaHome);
  const python = findSystemPython();
  if (!python) {
    fail(
      process.platform === "win32"
        ? "No encontré Python 3.11+ en este host. Instálalo y vuelve a ejecutar `melissa`."
        : "No encontré python3/python en este host. Instálalo y vuelve a ejecutar `melissa`."
    );
  }
  let result = runAndReturn(python.command, [...python.prefixArgs, "-m", "venv", runtimeDir]);
  if (typeof result.status === "number" && result.status !== 0) {
    process.exit(result.status);
  }
  runtime = resolveRuntime();
  if (!runtime) {
    fail(`No pude crear el runtime aislado en ${runtimeDir}`);
  }
  status("Instalando dependencias base de Melissa...");
  result = runAndReturn(runtime, ["-m", "pip", "install", "--disable-pip-version-check", "--upgrade", "pip"]);
  if (typeof result.status === "number" && result.status !== 0) {
    process.exit(result.status);
  }
  result = runAndReturn(runtime, ["-m", "pip", "install", "--disable-pip-version-check", "-r", path.join(repoDir, "requirements.txt")]);
  if (typeof result.status === "number" && result.status !== 0) {
    process.exit(result.status);
  }
  return runtime;
}

function bootstrapFromPackage() {
  status(`Sincronizando Melissa ${packageVersion} en ${melissaHome}...`);
  syncTree(packageRoot, repoDir);
  ensureDir(path.join(melissaHome, "instances"));
  ensureRuntime();
}

function needsBootstrap() {
  if (!fs.existsSync(entrypoint)) {
    return true;
  }
  if (!resolveRuntime()) {
    return true;
  }
  if (readInstalledVersion() !== packageVersion) {
    return true;
  }
  return process.env.MELISSA_FORCE_SYNC === "1";
}

function execMelissa(argv) {
  const runtime = resolveRuntime();
  if (!runtime || !fs.existsSync(entrypoint)) {
    return false;
  }
  const result = runAndReturn(
    runtime,
    [entrypoint, ...argv],
    {
      MELISSA_HOME: melissaHome,
      MELISSA_DIR: repoDir,
      INSTANCES_DIR: process.env.INSTANCES_DIR || path.join(melissaHome, "instances"),
      MELISSA_BACKUPS: process.env.MELISSA_BACKUPS || path.join(melissaHome, "backups"),
      MELISSA_SHARED_TELEGRAM_ROUTES:
        process.env.MELISSA_SHARED_TELEGRAM_ROUTES || path.join(repoDir, "shared_telegram_routes.json"),
    }
  );
  if (typeof result.status === "number") {
    process.exit(result.status);
  }
  process.exit(1);
}

if (needsBootstrap()) {
  bootstrapFromPackage();
}

if (!execMelissa(process.argv.slice(2))) {
  fail(`No pude iniciar Melissa desde ${melissaHome}`);
}
