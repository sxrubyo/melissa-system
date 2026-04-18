"""
Melissa V7.0 — Registry de Agentes
=====================================
Registra todos los agentes disponibles.
El orquestador los carga una sola vez al arranque.
"""

from __future__ import annotations
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from v7.agents.base import AgentBase

from v7.agents.captacion   import AgenteCaptacion
from v7.agents.objeciones  import AgenteObjeciones
from v7.agents.agenda      import AgenteAgenda
from v7.agents.conocimiento import AgenteConocimiento
from v7.agents.seguimiento import AgenteSeguimiento
from v7.agents.escalacion  import AgenteEscalacion
from v7.router             import AgentID


def build_registry(llm_engine) -> Dict[str, "AgentBase"]:
    """
    Construye el diccionario de agentes instanciados.
    Llamar UNA SOLA VEZ al arranque, pasar a MelissaUltra.
    """
    return {
        AgentID.CAPTACION:    AgenteCaptacion(llm_engine),
        AgentID.OBJECIONES:   AgenteObjeciones(llm_engine),
        AgentID.AGENDA:       AgenteAgenda(llm_engine),
        AgentID.CONOCIMIENTO: AgenteConocimiento(llm_engine),
        AgentID.SEGUIMIENTO:  AgenteSeguimiento(llm_engine),
        AgentID.ESCALACION:   AgenteEscalacion(llm_engine),
    }


__all__ = [
    "build_registry",
    "AgenteCaptacion",
    "AgenteObjeciones",
    "AgenteAgenda",
    "AgenteConocimiento",
    "AgenteSeguimiento",
    "AgenteEscalacion",
]
