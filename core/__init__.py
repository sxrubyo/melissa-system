"""
melissa/core/ — Clean public API for Melissa v9.0.

Exports the main engine components without requiring direct melissa.py imports.
This module bridges the legacy monolith (melissa.py) with the new modular architecture.
"""
from melissa_memory_engine import memory_engine, MelissaMemoryEngine
from melissa_uncertainty import uncertainty_detector, UncertaintyDetector
from melissa_voice import voice, MelissaVoice
from melissa_nova_proxy import NovaLLMProxy
from melissa_admin_api import router as admin_router
from melissa_cron import init_scheduler, shutdown_scheduler

__all__ = [
    "memory_engine",
    "MelissaMemoryEngine",
    "uncertainty_detector",
    "UncertaintyDetector",
    "voice",
    "MelissaVoice",
    "NovaLLMProxy",
    "admin_router",
    "init_scheduler",
    "shutdown_scheduler",
]
