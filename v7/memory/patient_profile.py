"""
Melissa V7.0 — Memoria Clínica Persistente
============================================
PatientProfile: perfil enriquecido del paciente (sobrevive reinicios).
FunnelState:    máquina de estados del proceso de conversión.

Diseño: capa delgada sobre el SQLite existente.
No reemplaza db.py — lo enriquece con lógica clínica.
"""

from __future__ import annotations
import json
import time
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

log = logging.getLogger(__name__)


# ── Máquina de estados del funnel ────────────────────────────────────────────

class FunnelStage(str, Enum):
    PRIMER_CONTACTO    = "primer_contacto"     # nunca ha escrito antes
    EXPLORANDO         = "explorando"           # haciendo preguntas, sin compromiso
    CON_INTENCION      = "con_intencion"        # expresó interés real
    CITA_AGENDADA      = "cita_agendada"        # tiene valoración agendada
    POST_CITA          = "post_cita"            # ya tuvo la valoración o procedimiento
    REACTIVACION       = "reactivacion"         # inactivo > 30 días, volvió


# Transiciones válidas — qué puede seguir a qué
_TRANSITIONS: Dict[FunnelStage, List[FunnelStage]] = {
    FunnelStage.PRIMER_CONTACTO: [FunnelStage.EXPLORANDO, FunnelStage.CON_INTENCION],
    FunnelStage.EXPLORANDO:      [FunnelStage.CON_INTENCION, FunnelStage.PRIMER_CONTACTO],
    FunnelStage.CON_INTENCION:   [FunnelStage.CITA_AGENDADA, FunnelStage.EXPLORANDO],
    FunnelStage.CITA_AGENDADA:   [FunnelStage.POST_CITA, FunnelStage.CON_INTENCION],
    FunnelStage.POST_CITA:       [FunnelStage.CON_INTENCION, FunnelStage.REACTIVACION],
    FunnelStage.REACTIVACION:    [FunnelStage.EXPLORANDO, FunnelStage.CON_INTENCION],
}


# ── Perfil del paciente ───────────────────────────────────────────────────────

@dataclass
class PatientProfile:
    chat_id:               str
    nombre:                Optional[str]        = None
    zona_interes:          List[str]            = field(default_factory=list)   # ["frente", "ojeras"]
    miedo_principal:       Optional[str]        = None                          # "quedar exagerada"
    objeciones_pasadas:    List[str]            = field(default_factory=list)   # ["precio", "tiempo"]
    funnel_stage:          FunnelStage          = FunnelStage.PRIMER_CONTACTO
    visitas:               int                  = 0
    ultima_interaccion:    float                = 0.0
    ultima_cita:           Optional[str]        = None
    procedimiento_hecho:   Optional[str]        = None
    score_conversion:      float                = 0.0                           # 0-1
    idioma:                str                  = "es"
    metadata:              Dict[str, Any]       = field(default_factory=dict)

    # ── Transición de funnel ──────────────────────────────────────────────────

    def advance_funnel(self, new_stage: FunnelStage) -> bool:
        """
        Avanza el funnel si la transición es válida.
        Devuelve True si se hizo la transición.
        """
        valid = _TRANSITIONS.get(self.funnel_stage, [])
        if new_stage in valid:
            log.info(
                "[funnel] %s: %s → %s",
                self.chat_id[:8], self.funnel_stage.value, new_stage.value
            )
            self.funnel_stage = new_stage
            return True
        return False

    def add_objecion(self, objecion: str) -> None:
        if objecion and objecion not in self.objeciones_pasadas:
            self.objeciones_pasadas.append(objecion)
            if len(self.objeciones_pasadas) > 10:
                self.objeciones_pasadas = self.objeciones_pasadas[-10:]

    def add_zona(self, zona: str) -> None:
        if zona and zona not in self.zona_interes:
            self.zona_interes.append(zona)

    def days_inactive(self) -> float:
        if not self.ultima_interaccion:
            return 999.0
        return (time.time() - self.ultima_interaccion) / 86400

    def to_context_summary(self, keys: List[str]) -> str:
        """
        Serializa solo los campos solicitados por el agente.
        Evita pasar 4,000 tokens cuando el agente solo necesita 200.
        """
        parts = []
        if "patient_name" in keys and self.nombre:
            parts.append(f"Nombre: {self.nombre}")
        if "visits" in keys:
            parts.append(f"Visitas: {self.visitas}")
        if "funnel_state" in keys:
            parts.append(f"Estado funnel: {self.funnel_stage.value}")
        if "objeciones_pasadas" in keys and self.objeciones_pasadas:
            parts.append(f"Objeciones previas: {', '.join(self.objeciones_pasadas)}")
        if "zona_interes" in keys and self.zona_interes:
            parts.append(f"Zona de interés: {', '.join(self.zona_interes)}")
        if "miedo_principal" in keys and self.miedo_principal:
            parts.append(f"Miedo principal: {self.miedo_principal}")
        if "ultima_cita" in keys and self.ultima_cita:
            parts.append(f"Última cita: {self.ultima_cita}")
        if "score_conversion" in keys:
            parts.append(f"Score conversión: {self.score_conversion:.0%}")
        return "\n".join(parts) if parts else ""

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["funnel_stage"] = self.funnel_stage.value
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "PatientProfile":
        if "funnel_stage" in data:
            try:
                data["funnel_stage"] = FunnelStage(data["funnel_stage"])
            except ValueError:
                data["funnel_stage"] = FunnelStage.PRIMER_CONTACTO
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# ── Capa de persistencia ──────────────────────────────────────────────────────

class ProfileStore:
    """
    Lee y escribe PatientProfile desde el SQLite existente.
    Usa la columna 'metadata' de la tabla patients para guardar el perfil V7.
    Sin migración de schema — retrocompatible con V6.
    """

    _PROFILE_KEY = "v7_profile"

    def __init__(self, db):
        self._db = db

    def load(self, chat_id: str) -> PatientProfile:
        """Carga el perfil. Si no existe, crea uno vacío."""
        try:
            patient_row = self._db.get_or_create_patient(chat_id)
            raw_meta = patient_row.get("metadata") or "{}"
            if isinstance(raw_meta, str):
                meta = json.loads(raw_meta)
            else:
                meta = raw_meta

            profile_data = meta.get(self._PROFILE_KEY)
            if profile_data:
                profile = PatientProfile.from_dict(profile_data)
            else:
                # Primera vez — construir desde campos existentes
                profile = PatientProfile(
                    chat_id=chat_id,
                    nombre=patient_row.get("name"),
                    visitas=patient_row.get("visits", 0),
                    idioma=patient_row.get("language", "es"),
                    ultima_interaccion=time.time(),
                )
            profile.chat_id = chat_id
            return profile
        except Exception as e:
            log.warning("[profile] error cargando %s: %s", chat_id[:8], e)
            return PatientProfile(chat_id=chat_id)

    def save(self, profile: PatientProfile) -> None:
        """Persiste el perfil en la columna metadata del paciente."""
        try:
            patient_row = self._db.get_or_create_patient(profile.chat_id)
            raw_meta = patient_row.get("metadata") or "{}"
            if isinstance(raw_meta, str):
                meta = json.loads(raw_meta)
            else:
                meta = dict(raw_meta)

            profile.ultima_interaccion = time.time()
            meta[self._PROFILE_KEY] = profile.to_dict()

            with self._db._conn() as c:
                c.execute(
                    "UPDATE patients SET metadata=?, name=? WHERE chat_id=?",
                    (json.dumps(meta), profile.nombre or "", profile.chat_id)
                )
        except Exception as e:
            log.error("[profile] error guardando %s: %s", profile.chat_id[:8], e)

    def update_funnel(self, chat_id: str, new_stage: FunnelStage) -> None:
        """Atajo para avanzar el funnel sin cargar todo el perfil."""
        profile = self.load(chat_id)
        if profile.advance_funnel(new_stage):
            self.save(profile)
