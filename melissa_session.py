"""
Módulo de gestión de sesiones demo para Melissa Ultra.

Contiene la lógica de sesiones demo incluyendo:
- Almacenamiento de estado de sesión (_demo_sessions)
- Generación de claves de sesión (bname_key, bctx_key, etc.)
- Métodos de gestión (get/set/clear)
- Limpieza de sesiones expiradas
- Detección de idioma del owner

Este módulo fue extraído de melissa.py para reducir su tamaño y mejorar mantenibilidad.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

try:
    from melissa_config import Config
except ImportError:
    class Config:
        DEMO_SESSION_TTL = 1800
        DEMO_MODE = False
        DEMO_BUSINESS_NAME = "tu negocio"
        DEMO_SECTOR = "estetica"


class SessionManager:
    """
    Gestor de sesiones demo para Melissa Ultra.
    
    Maneja el estado de sesiones demo de usuarios, incluyendo:
    - Nombre del negocio (bname_key)
    - Contexto/descripción del negocio (bctx_key)
    - Estado de búsqueda web (bfound_key, burl_key)
    - Tracking de tricks/demo commands (btrick_key)
    - Persona/archetype (bpersona_key)
    - Tono detectado (btone_key)
    - Modelo LLM preferido (bmodel_key)
    - Idioma del owner (blang_key)
    - Modo aprendizaje (blearn_key)
    - Modo simulación (bsim_key)
    """
    
    def __init__(self, sessions_dict: Dict[str, float] = None, emoji_chats_off: set = None):
        self._demo_sessions: Dict[str, float] = sessions_dict if sessions_dict is not None else {}
        self._emoji_chats_off: set = emoji_chats_off if emoji_chats_off is not None else set()
    
    def is_demo_mode_active(self) -> bool:
        """Verifica si hay sesiones demo activas."""
        now = time.time()
        return any(
            k.endswith("_ts") and (now - v) < Config.DEMO_SESSION_TTL
            for k, v in self._demo_sessions.items()
        )
    
    def get_demo_session(self, chat_id: str) -> Dict[str, any]:
        """
        Obtiene todos los valores de sesión para un chat_id.
        
        Args:
            chat_id: Identificador del chat
            
        Returns:
            Dict con todas las claves de sesión del demo
        """
        sk = f"demo_{chat_id}"
        keys = [
            f"{sk}_name", f"{sk}_ctx", f"{sk}_found", f"{sk}_url",
            f"{sk}_trick", f"{sk}_persona", f"{sk}_tone", f"{sk}_model",
            f"{sk}_owner_lang", f"{sk}_learn", f"{sk}_sim_mode"
        ]
        return {k.replace(sk + "_", ""): self._demo_sessions.get(k) for k in keys}
    
    def set_demo_session(self, chat_id: str, key: str, value: any) -> None:
        """
        Establece un valor en la sesión demo.
        
        Args:
            chat_id: Identificador del chat
            key: Clave (sin prefijo demo_{chat_id}_)
            value: Valor a almacenar
        """
        sk = f"demo_{chat_id}"
        self._demo_sessions[f"{sk}_{key}"] = value
        if key == "ts":
            self._touch_session(chat_id)
    
    def clear_demo_session(self, chat_id: str) -> None:
        """
        Limpia todos los datos de sesión para un chat_id.
        
        Args:
            chat_id: Identificador del chat
        """
        sk = f"demo_{chat_id}"
        keys_to_delete = [k for k in list(self._demo_sessions) if k.startswith(sk + "_")]
        for k in keys_to_delete:
            del self._demo_sessions[k]
    
    def _touch_session(self, chat_id: str) -> None:
        """Actualiza el timestamp de la sesión."""
        sk = f"demo_{chat_id}"
        self._demo_sessions[f"{sk}_ts"] = time.time()
    
    def cleanup_expired_sessions(self) -> int:
        """
        Limpia sesiones expiradas basándose en TTL.
        
        Returns:
            Número de sesiones limpiadas
        """
        now = time.time()
        ttl = Config.DEMO_SESSION_TTL
        
        expired_keys = []
        for k, v in self._demo_sessions.items():
            if k.endswith("_ts") and (now - v) > ttl * 2:
                expired_keys.append(k)
        
        for k in expired_keys:
            chat_id = k.replace("_ts", "").replace("demo_", "")
            self.clear_demo_session(chat_id)
        
        return len(expired_keys)
    
    def generate_session_keys(self, chat_id: str) -> Dict[str, str]:
        """
        Genera todas las claves de sesión para un chat_id.
        
        Args:
            chat_id: Identificador del chat
            
        Returns:
            Dict con todas las claves de sesión generadas
        """
        sk = f"demo_{chat_id}"
        return {
            "bname_key": sk + "_name",
            "bctx_key": sk + "_ctx",
            "bfound_key": sk + "_found",
            "burl_key": sk + "_url",
            "btrick_key": sk + "_trick",
            "bpersona_key": sk + "_persona",
            "btone_key": sk + "_tone",
            "bmodel_key": sk + "_model",
            "blang_key": sk + "_owner_lang",
            "blearn_key": sk + "_learn",
            "bsim_key": sk + "_sim_mode",
            "sk": sk,
        }
    
    def get_session_value(self, chat_id: str, key: str, default: any = None) -> any:
        """Obtiene un valor específico de la sesión."""
        sk = f"demo_{chat_id}"
        return self._demo_sessions.get(f"{sk}_{key}", default)
    
    def set_session_value(self, chat_id: str, key: str, value: any) -> None:
        """Establece un valor específico en la sesión."""
        sk = f"demo_{chat_id}"
        self._demo_sessions[f"{sk}_{key}"] = value
        self._touch_session(chat_id)

    def set_timestamp(self, chat_id: str) -> None:
        """Actualiza el timestamp de la sesión sin setear un valor de clave."""
        self._touch_session(chat_id)

    def touch_and_cleanup(self, chat_id: str) -> Tuple[bool, List[str]]:
        """
        Toca el timestamp y limpia sesiones expiradas.
        Retorna (is_new, keys_to_delete) donde keys_to_delete son las claves
        que deben borrarse si is_new=True.
        """
        now = time.time()
        ttl = Config.DEMO_SESSION_TTL
        sk = f"demo_{chat_id}"
        last_seen = self._demo_sessions.get(sk + "_ts", 0)
        is_new = (now - last_seen) > ttl
        self._demo_sessions[sk + "_ts"] = now

        self._demo_sessions = {
            k: v for k, v in self._demo_sessions.items()
            if not k.endswith("_ts") or (now - v) < ttl * 2
        }

        if is_new:
            keys_to_delete = [k for k in list(self._demo_sessions)
                              if k.startswith(sk + "_") and not k.endswith("_ts")]
        else:
            keys_to_delete = []
        return is_new, keys_to_delete
    
    def is_session_new(self, chat_id: str) -> bool:
        """Determina si la sesión es nueva (expiró el TTL)."""
        sk = f"demo_{chat_id}"
        now = time.time()
        last_seen = self._demo_sessions.get(sk + "_ts", 0)
        return (now - last_seen) > Config.DEMO_SESSION_TTL
    
    def reset_session(self, chat_id: str) -> None:
        """Resetea completamente la sesión (para expiración)."""
        sk = f"demo_{chat_id}"
        keys_del = [k for k in list(self._demo_sessions) 
                    if k.startswith(sk + "_") and not k.endswith("_ts")]
        for k in keys_del:
            del self._demo_sessions[k]
        self._touch_session(chat_id)


def _detect_demo_owner_language(raw_text: str, current_lang: str = "es") -> str:
    """
    Detecta el idioma del owner en modo demo basándose en señales explícitas.
    
    Args:
        raw_text: Mensaje original del usuario
        current_lang: Idioma actual detectado
        
    Returns:
        Código de idioma ('es', 'en', 'pt')
    """
    try:
        from melissa_helpers import _normalize_conv_text
    except ImportError:
        def _normalize_conv_text(s):
            return s.lower().strip() if s else ""
    
    normalized = _normalize_conv_text(raw_text or "")
    if not normalized:
        return current_lang or "es"
    
    explicit_en = (
        "just english sorry", "sorry just english", "english sorry",
        "english only", "speak english", "speak in english", 
        "i dont speak spanish", "i don t speak spanish",
        "i dont talk spanish", "i don t talk spanish",
        "no spanish", "only english", "what is this", "sorry what is this",
        "i dont understand", "i don t understand",
        "what did you say", "what did u say",
        "thats not my business", "that s not my business",
        "thats not us", "that s not us",
        "wrong business", "wrong company",
    )
    explicit_pt = (
        "só portugues", "so portugues", "falo portugues",
        "nao falo espanhol", "não falo espanhol",
    )
    
    if any(token in normalized for token in explicit_en):
        return "en"
    if any(token in normalized for token in explicit_pt):
        return "pt"
    
    try:
        from multilingual import MultilingualHandler
        detected = MultilingualHandler().detect(raw_text)
    except Exception:
        detected = "es"
    
    if current_lang in {"en", "pt"} and detected == "es" and len(normalized.split()) <= 6:
        return current_lang
    
    return detected if detected in {"es", "en", "pt"} else (current_lang or "es")


def _owner_confusion_or_language_signal(raw_text: str) -> bool:
    """
    Detecta señales de confusión del owner o cambio de idioma.
    
    Args:
        raw_text: Mensaje del usuario
        
    Returns:
        True si detecta señal de confusión/language switch
    """
    try:
        from melissa_helpers import _normalize_conv_text
    except ImportError:
        def _normalize_conv_text(s):
            return s.lower().strip() if s else ""
    
    normalized = _normalize_conv_text(raw_text or "")
    if not normalized:
        return False
    
    signals = (
        "just english sorry", "sorry just english", "english sorry",
        "english only", "speak english", "speak in english", "only english",
        "i dont speak spanish", "i don t speak spanish",
        "i dont talk spanish", "i don t talk spanish",
        "what is this", "sorry what is this",
        "i dont understand", "i don t understand",
        "what did you say", "what did u say",
        "thats not my business", "that s not my business",
        "that is not my business", "not my business",
        "thats not us", "that s not us", "that is not us", 
        "wrong business", "wrong company", "wrong one", "not the right one",
        "no hablo español", "no hablo espanol", 
        "solo ingles", "solo inglés",
    )
    return any(signal in normalized for signal in signals)


def _lang_text(es_text: str, en_text: str, pt_text: Optional[str] = None, 
               owner_lang: str = "es") -> str:
    """
    Retorna texto según el idioma del owner.
    
    Args:
        es_text: Texto en español
        en_text: Texto en inglés
        pt_text: Texto en portugués (opcional)
        owner_lang: Idioma del owner
        
    Returns:
        Texto en el idioma apropiado
    """
    if owner_lang == "en":
        return en_text
    if owner_lang == "pt" and pt_text is not None:
        return pt_text
    return es_text