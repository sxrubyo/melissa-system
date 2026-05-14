"""
melissa_nova_proxy.py — Transparent LLM proxy through Nova governance.
Wraps ALL outbound LLM calls so Nova can validate responses before delivery.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger("melissa.nova_proxy")


class NovaLLMProxy:
    """
    Transparent proxy that wraps LLM engine calls.
    Applies Nova governance AFTER LLM response is generated, BEFORE delivery.

    Usage:
        proxy = NovaLLMProxy(llm_engine, nova_guard)
        response, meta = await proxy.complete(messages, **kwargs)
    """

    def __init__(self, llm_engine, nova_guard=None, voice_engine=None,
                 uncertainty_detector=None, memory_engine=None):
        self._llm = llm_engine
        self._guard = nova_guard
        self._voice = voice_engine
        self._uncertainty = uncertainty_detector
        self._memory = memory_engine
        self._call_count = 0
        self._blocked_count = 0

    async def complete(
        self,
        messages: List[Dict[str, str]],
        *,
        model_tier: str = "fast",
        temperature: float = 0.7,
        max_tokens: int = 2048,
        use_cache: bool = True,
        instance_id: str = "",
        chat_id: str = "",
        inject_memory: bool = True,
        inject_thinking: bool = True,
        apply_voice: bool = True,
        **kwargs,
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Full pipeline: memory recall -> thinking injection -> LLM call ->
        Nova validation -> uncertainty check -> voice humanization.
        """
        self._call_count += 1
        meta = {"proxy": True, "instance_id": instance_id}
        start = time.time()

        working_messages = list(messages)

        # 1. Memory injection (prepend relevant context)
        if inject_memory and self._memory and instance_id and chat_id:
            try:
                user_msg = ""
                for m in reversed(working_messages):
                    if m.get("role") == "user":
                        user_msg = m["content"]
                        break
                if user_msg:
                    memories = await self._memory.recall_context(instance_id, user_msg, top_k=3)
                    if memories:
                        memory_text = "\n".join(
                            f"- [{m['ts'][:10]}] {' | '.join(msg['content'][:100] for msg in m['messages'][-2:])}"
                            for m in memories[:3]
                        )
                        memory_block = f"\nMEMORIA RELEVANTE (conversaciones anteriores):\n{memory_text}\n"
                        if working_messages and working_messages[0]["role"] == "system":
                            working_messages[0]["content"] += memory_block
                        else:
                            working_messages.insert(0, {"role": "system", "content": memory_block})
                        meta["memory_injected"] = len(memories)
            except Exception as e:
                log.debug(f"[nova_proxy] memory injection skipped: {e}")

        # 2. Thinking block injection
        if inject_thinking and self._voice:
            try:
                if working_messages and working_messages[0]["role"] == "system":
                    working_messages[0]["content"] = self._voice.inject_thinking_block(
                        working_messages[0]["content"]
                    )
                    meta["thinking_injected"] = True
            except Exception:
                pass

        # 3. LLM call
        if not self._llm:
            return "", {"error": "no_llm_engine"}

        response, llm_meta = await self._llm.complete(
            working_messages,
            model_tier=model_tier,
            temperature=temperature,
            max_tokens=max_tokens,
            use_cache=use_cache,
            **kwargs,
        )
        meta.update(llm_meta)

        # 4. Nova governance check (validate response before delivery)
        if self._guard and response:
            try:
                ok, reason, ledger_id = await self._guard.should_send(
                    response[:500],
                    patient_chat_id=chat_id,
                    context=instance_id,
                )
                meta["nova_verdict"] = "approved" if ok else "blocked"
                meta["nova_reason"] = reason
                if ledger_id:
                    meta["nova_ledger_id"] = ledger_id
                if not ok:
                    self._blocked_count += 1
                    log.info(f"[nova_proxy] response BLOCKED: {reason}")
                    response = self._generate_safe_fallback(reason)
                    meta["nova_fallback"] = True
            except Exception as e:
                log.debug(f"[nova_proxy] guard check skipped: {e}")
                meta["nova_verdict"] = "skipped"

        # 5. Uncertainty detection
        if self._uncertainty and response:
            try:
                user_msg = ""
                for m in reversed(messages):
                    if m.get("role") == "user":
                        user_msg = m["content"]
                        break
                confidence = self._uncertainty.confidence_score(response, user_msg, messages)
                meta["confidence"] = confidence
                if confidence < self._uncertainty.threshold:
                    meta["low_confidence"] = True
                    await self._uncertainty.log_gap(
                        instance_id, user_msg, response, confidence, chat_id
                    )
            except Exception as e:
                log.debug(f"[nova_proxy] uncertainty check skipped: {e}")

        # 6. Voice humanization
        if apply_voice and self._voice and response:
            try:
                response = self._voice.humanize(response)
                meta["voice_applied"] = True
            except Exception:
                pass

        meta["total_ms"] = int((time.time() - start) * 1000)
        return response, meta

    def _generate_safe_fallback(self, reason: str) -> str:
        """Generate a safe response when Nova blocks the original."""
        if "medical" in reason.lower() or "diagnos" in reason.lower():
            return "Para esa consulta específica te recomiendo hablar directamente con el especialista. Quieres que te ayude a agendar?"
        if "price" in reason.lower() or "precio" in reason.lower():
            return "Los precios dependen de la valoración personalizada. Te agendo una cita para que te den toda la información?"
        return "Déjame verificar eso y te confirmo. Mientras tanto, hay algo más en lo que te pueda ayudar?"

    def get_stats(self) -> Dict[str, int]:
        return {
            "total_calls": self._call_count,
            "blocked": self._blocked_count,
        }
