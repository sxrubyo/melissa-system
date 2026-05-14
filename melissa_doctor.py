#!/usr/bin/env python3
"""melissa_doctor.py — Health check + auto-heal for Melissa instances."""
import asyncio, json, os, subprocess, sys, time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import httpx

def color(text, code): return f"\033[{code}m{text}\033[0m"
def green(text): return color(text, "32")
def yellow(text): return color(text, "33")
def red(text): return color(text, "31")
def dim(text): return color(text, "90")
def bold(text): return color(text, "1")

class HealthCheck:
    def __init__(self, name: str, status: str, message: str = ""):
        self.name = name
        self.status = status  # "ok" | "warning" | "error"
        self.message = message

    def __str__(self):
        icon = {"ok": green("✓"), "warning": yellow("⚠"), "error": red("✗")}[self.status]
        msg = f" ({self.message})" if self.message else ""
        return f"  {icon} {self.name}{dim(msg)}"


class MelissaDoctor:
    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.checks: List[HealthCheck] = []

    async def run_all_checks(self) -> List[HealthCheck]:
        self.checks = []
        await asyncio.gather(
            self._check_pm2(),
            self._check_api_health(),
            self._check_llm_latency(),
            self._check_persona(),
            self._check_memory(),
            self._check_knowledge_gaps(),
            self._check_whatsapp(),
        )
        return self.checks

    async def _check_pm2(self):
        try:
            result = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=5)
            processes = json.loads(result.stdout)
            for p in processes:
                if self.instance_id in p.get("name", ""):
                    status = p.get("pm2_env", {}).get("status", "unknown")
                    uptime = p.get("pm2_env", {}).get("pm_uptime", 0)
                    if status == "online":
                        uptime_str = self._format_uptime(uptime)
                        self.checks.append(HealthCheck("PM2 instance", "ok", f"online, uptime: {uptime_str}"))
                    else:
                        self.checks.append(HealthCheck("PM2 instance", "error", f"status: {status}"))
                    return
            self.checks.append(HealthCheck("PM2 instance", "error", "not found"))
        except Exception as e:
            self.checks.append(HealthCheck("PM2 instance", "error", str(e)))

    async def _check_api_health(self):
        port = self._get_port()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"http://localhost:{port}/health")
                if r.status_code == 200:
                    data = r.json()
                    self.checks.append(HealthCheck("API health", "ok", f"v{data.get('version', '?')}"))
                else:
                    self.checks.append(HealthCheck("API health", "error", f"HTTP {r.status_code}"))
        except Exception as e:
            self.checks.append(HealthCheck("API health", "error", str(e)[:50]))

    async def _check_llm_latency(self):
        port = self._get_port()
        key = os.getenv("MASTER_API_KEY", "melissa_master_2026_santiago")
        try:
            start = time.time()
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(f"http://localhost:{port}/test",
                                      json={"message": "hola", "chat_id": "doctor_test"},
                                      headers={"X-Master-Key": key, "Content-Type": "application/json"})
            latency = time.time() - start
            if r.status_code == 200 and latency < 10:
                self.checks.append(HealthCheck("LLM response", "ok", f"avg {latency:.1f}s"))
            elif r.status_code == 200:
                self.checks.append(HealthCheck("LLM response", "warning", f"slow: {latency:.1f}s"))
            else:
                self.checks.append(HealthCheck("LLM response", "error", f"HTTP {r.status_code}"))
        except Exception as e:
            self.checks.append(HealthCheck("LLM response", "error", str(e)[:50]))

    async def _check_persona(self):
        persona_paths = [
            Path(f"/home/ubuntu/melissa-instances/{self.instance_id}/personas/persona.yaml"),
            Path(f"/home/ubuntu/melissa/personas/{self.instance_id}/persona.yaml"),
            Path(f"/home/ubuntu/melissa/personas/{self.instance_id}/runtime_override.json"),
        ]
        for p in persona_paths:
            if p.exists():
                age_hours = (time.time() - p.stat().st_mtime) / 3600
                self.checks.append(HealthCheck("Persona", "ok", f"loaded (modified {age_hours:.0f}h ago)"))
                return
        self.checks.append(HealthCheck("Persona", "warning", "no persona file found"))

    async def _check_memory(self):
        memory_dir = Path("memory_store") / self.instance_id
        if memory_dir.exists():
            episodic = list((memory_dir / "episodic").glob("*.jsonl")) if (memory_dir / "episodic").exists() else []
            turns = sum(1 for f in episodic for _ in open(f))
            self.checks.append(HealthCheck("Memory engine", "ok", f"{turns} turns stored"))
        else:
            self.checks.append(HealthCheck("Memory engine", "warning", "no data yet"))

    async def _check_knowledge_gaps(self):
        gaps_dir = Path("knowledge_gaps")
        if not gaps_dir.exists():
            self.checks.append(HealthCheck("Knowledge gaps", "ok", "none"))
            return
        today = datetime.now().strftime("%Y-%m-%d")
        today_file = gaps_dir / f"{today}.jsonl"
        if today_file.exists():
            count = sum(1 for _ in open(today_file))
            if count > 5:
                self.checks.append(HealthCheck("Knowledge gaps", "warning", f"{count} unresolved today"))
            else:
                self.checks.append(HealthCheck("Knowledge gaps", "ok", f"{count} today"))
        else:
            self.checks.append(HealthCheck("Knowledge gaps", "ok", "none today"))

    async def _check_whatsapp(self):
        port = self._get_port()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"http://localhost:{port}/health")
                if r.status_code == 200:
                    data = r.json()
                    wa = data.get("whatsapp", {})
                    if wa.get("connected"):
                        self.checks.append(HealthCheck("WhatsApp bridge", "ok", "connected"))
                    elif wa:
                        self.checks.append(HealthCheck("WhatsApp bridge", "warning", "disconnected"))
                    else:
                        self.checks.append(HealthCheck("WhatsApp bridge", "warning", "not configured"))
        except:
            self.checks.append(HealthCheck("WhatsApp bridge", "error", "cannot reach API"))

    def _get_port(self) -> int:
        # Try to read from instance .env
        env_path = Path(f"/home/ubuntu/melissa-instances/{self.instance_id}/.env")
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("PORT="):
                    return int(line.split("=")[1].strip())
        # Default: main instance on 8001
        if self.instance_id in ("default", "melissa"):
            return 8001
        return 8003

    def _format_uptime(self, pm_uptime_ms: int) -> str:
        seconds = (time.time() * 1000 - pm_uptime_ms) / 1000
        if seconds < 3600:
            return f"{int(seconds/60)}m"
        elif seconds < 86400:
            return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"
        else:
            return f"{int(seconds/86400)}d {int((seconds%86400)/3600)}h"

    def print_report(self):
        print()
        print(bold(f"🔍 Melissa Doctor — {self.instance_id}"))
        print("─" * 45)
        for check in self.checks:
            print(str(check))
        print("─" * 45)
        ok = sum(1 for c in self.checks if c.status == "ok")
        warn = sum(1 for c in self.checks if c.status == "warning")
        err = sum(1 for c in self.checks if c.status == "error")
        total = len(self.checks)
        health_pct = int((ok / total) * 100) if total else 0
        print(f"  Health: {health_pct}% | {green(f'{ok} ok')} {yellow(f'{warn} warnings') if warn else ''} {red(f'{err} errors') if err else ''}")
        print()

    async def auto_heal(self):
        """Attempt to fix critical issues."""
        healed = []
        for check in self.checks:
            if check.status != "error":
                continue
            if "PM2" in check.name and "not found" not in check.message:
                try:
                    subprocess.run(["pm2", "restart", f"melissa-{self.instance_id}"], capture_output=True, timeout=10)
                    healed.append(f"Restarted PM2: melissa-{self.instance_id}")
                except:
                    pass
        if healed:
            print(bold("🔧 Auto-heal actions:"))
            for h in healed:
                print(f"  {green('→')} {h}")
        return healed


async def main():
    import argparse
    parser = argparse.ArgumentParser(prog="melissa doctor", description="Health check for Melissa instances")
    parser.add_argument("instance", nargs="?", default="melissa", help="Instance ID to check")
    parser.add_argument("--fix", action="store_true", help="Attempt auto-heal for errors")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    doctor = MelissaDoctor(args.instance)
    await doctor.run_all_checks()

    if args.json:
        print(json.dumps([{"name": c.name, "status": c.status, "message": c.message} for c in doctor.checks], indent=2))
    else:
        doctor.print_report()

    if args.fix:
        await doctor.auto_heal()

if __name__ == "__main__":
    asyncio.run(main())
