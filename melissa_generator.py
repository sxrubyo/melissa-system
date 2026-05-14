"""
Módulo de generación LLM para Melissa Ultra.

Contiene la lógica de generación de respuestas:
- _llm(): Generación básica
- _llm_conv_pitch(): Generación con pitch para prospectos confuse
- _llm_conv(): Generación conversacional con historial
- _demo_llm_conv_quality_chain(): Chain con validación y repair
- _demo_llm_quality_chain(): Chain de calidad con retries

Este módulo fue extraído de melissa.py para reducir su tamaño y mejorar mantenibilidad.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from melissa_config import Config
except ImportError:
    class Config:
        GROQ_API_KEY = ""
        GEMINI_API_KEY = ""
        GEMINI_API_KEY_2 = ""
        GEMINI_API_KEY_3 = ""
        OPENROUTER_API_KEY = ""


class GeneratorManager:
    """
    Gestor de generación LLM para Melissa Ultra.
    
    Proporciona métodos para:
    - Generación básica de texto
    - Generación conversacional con historial
    - Generación con pitch especializado
    - Chains de calidad con validación y retry
    """
    
    def __init__(self, llm_engine=None, generator=None):
        self._llm_engine = llm_engine
        self._generator = generator
    
    def _get_demo_engine(self, demo_model_pref: str = "auto", bmodel_key: str = ""):
        """
        Devuelve el proveedor LLM según preferencia de sesión.
        
        Formatos soportados:
          auto                    → engine global
          gemini                  → GeminiProvider con gemini-2.5-flash
          gemini:gemini-2.5-pro   → GeminiProvider con modelo específico
          groq                    → GroqProvider con llama-3.3-70b-versatile
          groq:llama-3.1-8b-instant → GroqProvider con modelo específico
          openrouter              → OpenRouterProvider
          openrouter:anthropic/claude-sonnet-4 → OpenRouter con modelo específico
        """
        from llm_engine import (
            GeminiProvider, GroqProvider, OpenRouterProvider
        )
        
        pref = demo_model_pref
        
        if ":" in pref:
            provider, model_name = pref.split(":", 1)
        else:
            provider, model_name = pref, None
        
        if provider == "groq" and Config.GROQ_API_KEY:
            eng = GroqProvider(Config.GROQ_API_KEY)
            if model_name:
                eng.MDLS = {"reasoning": model_name, "fast": model_name, "lite": model_name}
            return eng
        
        elif provider == "gemini":
            key = Config.GEMINI_API_KEY or Config.GEMINI_API_KEY_2 or Config.GEMINI_API_KEY_3
            if key:
                eng = GeminiProvider(key, "gemini_demo")
                if model_name:
                    eng.MDLS = {"reasoning": model_name, "fast": model_name, "lite": model_name}
                else:
                    eng.MDLS = {
                        "reasoning": "gemini-2.5-flash", 
                        "fast": "gemini-2.5-flash", 
                        "lite": "gemini-2.5-flash-lite"
                    }
                return eng
            if Config.OPENROUTER_API_KEY:
                eng = OpenRouterProvider(Config.OPENROUTER_API_KEY)
                m = model_name or "google/gemini-2.5-flash"
                eng.MDLS = {"reasoning": m, "fast": m, "lite": m}
                return eng
        
        elif provider == "openrouter" and Config.OPENROUTER_API_KEY:
            eng = OpenRouterProvider(Config.OPENROUTER_API_KEY)
            if model_name:
                eng.MDLS = {"reasoning": model_name, "fast": model_name, "lite": model_name}
            return eng
        
        return self._llm_engine or (self._generator.llm if self._generator else None)
    
    async def _llm(
        self,
        sys_p: str,
        usr_p: str,
        temp: float = 0.82,
        max_t: int = 8192,
        model_tier: str = "fast",
        demo_model_pref: str = "auto"
    ) -> Optional[str]:
        """
        Generación básica de texto con LLM.
        
        Args:
            sys_p: Prompt del sistema
            usr_p: Prompt del usuario
            temp: Temperatura de generación
            max_t: Máximo de tokens de salida
            model_tier: Tier del modelo (fast, reasoning, lite)
            demo_model_pref: Preferencia de modelo demo
            
        Returns:
            Texto generado o None en caso de error
        """
        import logging
        log = logging.getLogger("melissa_generator")
        
        msgs = [{"role": "system", "content": sys_p}, {"role": "user", "content": usr_p}]
        
        try:
            eng = self._get_demo_engine(demo_model_pref)
            if not eng:
                raise RuntimeError("LLM no init")
            
            r, meta = await eng.complete(
                msgs,
                model_tier=model_tier,
                temperature=temp,
                max_tokens=max_t,
                use_cache=False,
            )
            
            log.info(f"[demo] {meta.get('provider','?')} model={meta.get('model','?')[:30]}")
            
            if self._generator:
                return self._generator._postprocess(r, self._generator.PersonalityProfile())
            return r
            
        except Exception as e:
            log.error(f"[demo] llm error: {e}")
            return None
    
    async def _llm_conv_pitch(
        self,
        pitch_sys: str,
        history: List[Dict[str, Any]],
        text: str,
        temp: float = 0.85,
        max_t: int = 8192,
        recent_limit: int = 12,
        demo_model_pref: str = "auto"
    ) -> Optional[str]:
        """
        LLM con el pitch de Black One para prospectos confundidos.
        
        Args:
            pitch_sys: Prompt de sistema con el pitch
            history: Historial de conversación
            text: Mensaje actual
            temp: Temperatura
            max_t: Máximo de tokens
            recent_limit: Límite de mensajes recientes a incluir
            demo_model_pref: Preferencia de modelo
            
        Returns:
            Texto generado o None
        """
        import logging
        log = logging.getLogger("melissa_generator")
        
        msgs = [{"role": "system", "content": pitch_sys}]
        for m in history[-recent_limit:]:
            msgs.append({"role": m["role"], "content": m["content"]})
        msgs.append({"role": "user", "content": text})
        
        try:
            eng = self._get_demo_engine(demo_model_pref)
            if not eng:
                raise RuntimeError("LLM no init")
            
            r, meta = await eng.complete(
                msgs,
                model_tier="fast",
                temperature=temp,
                max_tokens=max_t,
                use_cache=False
            )
            
            log.info(f"[demo][pitch] {meta.get('provider','?')}")
            
            if self._generator:
                return self._generator._postprocess(r, self._generator.PersonalityProfile())
            return r
            
        except Exception as e:
            log.error(f"[demo][pitch] error: {e}")
            return None
    
    async def _llm_conv(
        self,
        sys_p: str,
        history: List[Dict[str, Any]],
        text: str,
        temp: float = 0.85,
        max_t: int = 8192,
        model_tier: str = "fast",
        recent_limit: int = 12,
        demo_model_pref: str = "auto"
    ) -> Optional[str]:
        """
        Generación conversacional con historial.
        
        Args:
            sys_p: Prompt del sistema
            history: Historial de conversación
            text: Mensaje actual
            temp: Temperatura
            max_t: Máximo de tokens
            model_tier: Tier del modelo
            recent_limit: Límite de mensajes recientes
            demo_model_pref: Preferencia de modelo
            
        Returns:
            Texto generado o None
        """
        import logging
        log = logging.getLogger("melissa_generator")
        
        msgs = [{"role": "system", "content": sys_p}]
        for m in history[-recent_limit:]:
            msgs.append({"role": m["role"], "content": m["content"]})
        msgs.append({"role": "user", "content": text})
        
        try:
            eng = self._get_demo_engine(demo_model_pref)
            if not eng:
                raise RuntimeError("LLM no init")
            
            r, meta = await eng.complete(
                msgs,
                model_tier=model_tier,
                temperature=temp,
                max_tokens=max_t,
                use_cache=False,
            )
            
            log.info(f"[demo] {meta.get('provider','?')} model={meta.get('model','?')[:30]}")
            
            if self._generator:
                return self._generator._postprocess(r, self._generator.PersonalityProfile())
            return r
            
        except Exception as e:
            log.error(f"[demo] llm_conv error: {e}")
            return None
    
    async def _demo_llm_conv_quality_chain(
        self,
        system_prompt: str,
        validator: Callable[[str], bool],
        repair_instructions: str,
        history: List[Dict[str, Any]],
        text: str,
        temp: float = 0.72,
        max_t: int = 8192,
        model_tier: str = "fast",
        recent_limit: int = 8,
        demo_model_pref: str = "auto"
    ) -> Tuple[Optional[str], bool]:
        """
        Chain de calidad con validación y repair para conversaciones demo.
        
        Intenta primero la generación normal, si falla la validación
        reintenta con instrucciones de repair.
        
        Args:
            system_prompt: Prompt del sistema
            validator: Función que valida la respuesta
            repair_instructions: Instrucciones para repair si falla validación
            history: Historial de conversación
            text: Mensaje actual
            temp: Temperatura
            max_t: Máximo de tokens
            model_tier: Tier del modelo
            recent_limit: Límite de mensajes recientes
            demo_model_pref: Preferencia de modelo
            
        Returns:
            Tuple (respuesta_valida o None, tuvo_output)
        """
        import logging
        log = logging.getLogger("melissa_generator")
        
        _chain_start = time.time()
        _CHAIN_TIMEOUT_S = 45  # Timeout entre intentos
        
        attempts = [
            (system_prompt, temp, max_t, model_tier, recent_limit),
            (
                system_prompt
                + "\n\nREPARA LA RESPUESTA:\n"
                + repair_instructions.strip()
                + "\n- no repitas introducciones\n- no suenes a bot ni a guion de demo",
                0.58,
                max_t,
                "reasoning",
                recent_limit,
            ),
        ]
        
        had_output = False
        
        for prompt_now, temp_now, max_now, tier_now, limit_now in attempts:
            if time.time() - _chain_start > _CHAIN_TIMEOUT_S:
                log.warning("[demo] conv_quality_chain abortada por timeout (%ds)", _CHAIN_TIMEOUT_S)
                break
            
            candidate = await self._llm_conv(
                prompt_now,
                history=history,
                text=text,
                temp=temp_now,
                max_t=max_now,
                model_tier=tier_now,
                recent_limit=limit_now,
                demo_model_pref=demo_model_pref,
            )
            
            if candidate and candidate.strip():
                had_output = True
                if validator(candidate):
                    return candidate, True
        
        return None, had_output
    
    async def _demo_llm_quality_chain(
        self,
        system_prompt: str,
        validator: Callable[[str], bool],
        repair_instructions: str,
        user_message: str,
        temp: float = 0.72,
        max_t: int = 8192,
        model_tier: str = "fast",
        demo_model_pref: str = "auto"
    ) -> Tuple[Optional[str], bool]:
        """
        Chain de calidad simple (sin historial) para generación demo.
        
        Args:
            system_prompt: Prompt del sistema
            validator: Función que valida la respuesta
            repair_instructions: Instrucciones para repair
            user_message: Mensaje del usuario
            temp: Temperatura
            max_t: Máximo de tokens
            model_tier: Tier del modelo
            demo_model_pref: Preferencia de modelo
            
        Returns:
            Tuple (respuesta o None, tuvo_output)
        """
        import logging
        log = logging.getLogger("melissa_generator")
        
        _chain_start = time.time()
        _CHAIN_TIMEOUT_S = 45
        
        attempts = [
            (system_prompt, temp, max_t, model_tier),
            (
                system_prompt
                + "\n\nREPARA LA RESPUESTA:\n"
                + repair_instructions.strip()
                + "\n- no repitas introducciones\n- no suenes a bot",
                0.58,
                max_t,
                "reasoning",
            ),
        ]
        
        had_output = False
        
        for prompt_now, temp_now, max_now, tier_now in attempts:
            if time.time() - _chain_start > _CHAIN_TIMEOUT_S:
                log.warning("[demo] quality_chain abortada por timeout")
                break
            
            candidate = await self._llm(
                prompt_now,
                user_message,
                temp=temp_now,
                max_t=max_now,
                model_tier=tier_now,
                demo_model_pref=demo_model_pref,
            )
            
            if candidate and candidate.strip():
                had_output = True
                if validator(candidate):
                    return candidate, True
        
        return None, had_output


def estimate_tokens(text: str) -> int:
    """
    Estima el número de tokens en un texto.
    
    Args:
        text: Texto a estimar
        
    Returns:
        Estimación de tokens (approx 4 chars por token)
    """
    return len(text) // 4


def budget_tokens(
    system_prompt: str,
    max_t: int = 8192,
    safety_margin: float = 0.9
) -> Tuple[int, int]:
    """
    Calcula presupuesto de tokens para generación.
    
    Args:
        system_prompt: Prompt del sistema
        max_t: Máximo de tokens disponibles
        safety_margin: Margen de seguridad (0.0-1.0)
        
    Returns:
        Tuple (tokens_disponibles_output, tokens_reservados)
    """
    system_tokens = estimate_tokens(system_prompt)
    available = int(max_t * safety_margin)
    output_budget = max(available - system_tokens, 512)
    return output_budget, system_tokens