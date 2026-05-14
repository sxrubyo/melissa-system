"""melissa_integrations/vault.py — Central credential vault for all integrations."""
from __future__ import annotations
import json, logging, os
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger("melissa.vault")

VAULT_DIR = Path("integrations/vault")


class IntegrationVault:
    """
    Per-instance credential manager. If API key exists -> integration active.
    If not -> feature silently disabled. Zero errors shown to end user.
    """

    def __init__(self, instance_id: str):
        self.instance_id = instance_id
        self.active: Dict[str, Any] = {}
        self._vault_dir = VAULT_DIR / instance_id
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        """Load credentials from manifest."""
        manifest_path = self._vault_dir / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text())
            for service_name, config in manifest.items():
                if config.get("enabled", True):
                    self.active[service_name] = config
                    log.info(f"[vault] {self.instance_id}: {service_name} active")
        except Exception as e:
            log.warning(f"[vault] failed to load manifest for {self.instance_id}: {e}")

    def get(self, service_name: str) -> Optional[Dict]:
        """Get integration config. Returns None if not active."""
        return self.active.get(service_name)

    def is_active(self, service_name: str) -> bool:
        return service_name in self.active

    async def add(self, service_name: str, credentials: Dict) -> bool:
        """Add or update an integration credential."""
        self.active[service_name] = {**credentials, "enabled": True, "added_at": __import__("time").time()}
        self._save_manifest()
        log.info(f"[vault] added {service_name} for {self.instance_id}")
        return True

    async def remove(self, service_name: str) -> bool:
        """Remove an integration."""
        if service_name in self.active:
            del self.active[service_name]
            self._save_manifest()
            log.info(f"[vault] removed {service_name} from {self.instance_id}")
            return True
        return False

    def list_active(self) -> list:
        """List all active integrations."""
        return list(self.active.keys())

    def _save_manifest(self):
        manifest_path = self._vault_dir / "manifest.json"
        manifest_path.write_text(json.dumps(self.active, ensure_ascii=False, indent=2))


# Cache of vaults per instance
_vaults: Dict[str, IntegrationVault] = {}

def get_vault(instance_id: str) -> IntegrationVault:
    if instance_id not in _vaults:
        _vaults[instance_id] = IntegrationVault(instance_id)
    return _vaults[instance_id]
