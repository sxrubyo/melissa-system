from __future__ import annotations
import logging
import asyncio
import re
import json
import time
import random
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

log = logging.getLogger("melissa.demo")

class MelissaDemo:
    """
    Componente especializado para el Modo Demo.
    Maneja la experiencia de intriga progresiva y trucos de venta.
    """
    
    def __init__(self, melissa):
        self.melissa = melissa

    async def handle(self, chat_id: str, text: str, clinic: Dict, 
                    attachments: Optional[List[Dict[str, Any]]] = None) -> List[str]:
        """MODO DEMO — Delegamos a la lógica original por ahora."""
        # Para máxima estabilidad, llamamos al método en melissa.py que ya conocemos.
        return await self.melissa._handle_demo_message(chat_id, text, clinic, attachments)
