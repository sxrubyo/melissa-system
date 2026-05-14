"""melissa_calendar.py — Google Calendar: check availability + book appointments."""
from __future__ import annotations
import json, logging, os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import httpx

log = logging.getLogger("melissa.calendar")

VAULT_DIR = Path("integrations/vault")


class MelissaCalendar:
    """Google Calendar integration for booking appointments."""

    def __init__(self, instance_id: str = "default"):
        self.instance_id = instance_id
        self._tokens_file = VAULT_DIR / instance_id / "google_tokens.json"
        self._creds_file = VAULT_DIR / instance_id / "google_credentials.json"

    @property
    def is_connected(self) -> bool:
        return self._tokens_file.exists()

    async def _get_access_token(self) -> Optional[str]:
        """Get valid access token (refresh if needed)."""
        if not self._tokens_file.exists():
            return None
        tokens = json.loads(self._tokens_file.read_text())
        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            return tokens.get("access_token")

        # Load client creds
        if not self._creds_file.exists():
            return tokens.get("access_token")
        creds_data = json.loads(self._creds_file.read_text())
        inner = creds_data.get("installed") or creds_data.get("web") or creds_data
        client_id = inner.get("client_id", "")
        client_secret = inner.get("client_secret", "")

        if not client_id:
            return tokens.get("access_token")

        # Refresh
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post("https://oauth2.googleapis.com/token", data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                })
                if r.status_code == 200:
                    new = r.json()
                    tokens["access_token"] = new["access_token"]
                    self._tokens_file.write_text(json.dumps(tokens, indent=2))
                    return new["access_token"]
        except Exception as e:
            log.warning(f"[calendar] refresh failed: {e}")

        return tokens.get("access_token")

    async def get_availability(self, date: str = None, days_ahead: int = 3) -> List[Dict]:
        """Get available slots for the next N days."""
        token = await self._get_access_token()
        if not token:
            return []

        if not date:
            start = datetime.now()
        else:
            try:
                start = datetime.strptime(date, "%Y-%m-%d")
            except:
                start = datetime.now()

        end = start + timedelta(days=days_ahead)
        time_min = start.isoformat() + "Z"
        time_max = end.isoformat() + "Z"

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"timeMin": time_min, "timeMax": time_max,
                            "singleEvents": "true", "orderBy": "startTime"},
                )
                if r.status_code == 200:
                    events = r.json().get("items", [])
                    return [{"summary": e.get("summary", "Ocupado"),
                             "start": e.get("start", {}).get("dateTime", ""),
                             "end": e.get("end", {}).get("dateTime", "")}
                            for e in events]
                else:
                    log.warning(f"[calendar] events fetch failed: {r.status_code}")
                    return []
        except Exception as e:
            log.error(f"[calendar] error: {e}")
            return []

    async def create_appointment(self, patient_name: str, phone: str,
                                  service: str, date_time: str,
                                  duration_minutes: int = 30) -> Optional[str]:
        """Create a calendar event for an appointment."""
        token = await self._get_access_token()
        if not token:
            return None

        try:
            start_dt = datetime.fromisoformat(date_time)
        except:
            return None

        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": f"Cita: {patient_name} — {service}",
            "description": f"Paciente: {patient_name}\nTeléfono: {phone}\nServicio: {service}\nAgendado por: Melissa AI",
            "start": {"dateTime": start_dt.isoformat(), "timeZone": "America/Bogota"},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": "America/Bogota"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "popup", "minutes": 1440},
                ],
            },
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(
                    "https://www.googleapis.com/calendar/v3/calendars/primary/events",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=event,
                )
                if r.status_code in (200, 201):
                    created = r.json()
                    log.info(f"[calendar] appointment created: {created.get('id')}")
                    return created.get("id")
                else:
                    log.error(f"[calendar] create failed: {r.status_code} {r.text[:200]}")
                    return None
        except Exception as e:
            log.error(f"[calendar] create error: {e}")
            return None

    async def get_availability_summary(self, days_ahead: int = 3) -> str:
        """Get human-readable availability summary for Melissa to use."""
        events = await self.get_availability(days_ahead=days_ahead)
        if not events:
            return "sin citas programadas los próximos días — disponibilidad abierta"

        busy_times = []
        for e in events[:10]:
            start = e.get("start", "")
            if start:
                try:
                    dt = datetime.fromisoformat(start.replace("Z", ""))
                    busy_times.append(f"{dt.strftime('%A %d')} a las {dt.strftime('%I:%M%p')}: {e['summary']}")
                except:
                    pass

        if busy_times:
            return "Citas existentes:\n" + "\n".join(busy_times)
        return "calendario disponible"
