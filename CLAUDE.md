## Nova Governance Rules
_These rules are automatically enforced by Nova. Do not remove._

- [NEVER] Never modify, delete, or overwrite .nova
- [NEVER] Never modify, delete, or overwrite .ssh
- [NEVER] Modify, delete, or overwrite files in .nova
- [NEVER] Modify, delete, or overwrite files in .ssh

## Melissa Project Rules

- Nova NEVER imports from melissa — it wraps from outside as transparent proxy
- melissa_brain_v10.py is SINGLE source of truth for conversation history
- All LLM calls should pass through melissa_nova_proxy.py when governance is needed
- Multi-tenant: NEVER mix data between instances (each has isolated SQLite + .env)
- PM2 instances: check ecosystem.config.js before touching any paths
- When uncertain about an import or connection: investigate with grep/find first
- Anti-robot: responses must NEVER contain "como IA", "no tengo capacidad", "está fuera de mi alcance"
- Test with: pm2 logs melissa --lines 50 after every change
- After every file edit: verify with py_compile before moving on
- Run pytest tests/ before committing

## Architecture Quick Reference

```
Ports: 8001 (melissa/demo), 8003 (clinica/prod), 8002 (wa-bridge), 9001 (nova)
Entry: melissa.py → process_message() → demo_mgr/admin_mgr/production_mgr
Admin API: POST /admin/{id}/persona, /model, /teach, /gaps, /status
Memory: melissa_memory_engine.py (episodic/semantic/procedural, TF-IDF recall)
Voice: melissa_voice.py (robot pattern removal, humanization)
Cron: melissa_cron.py (weekly consolidation Sun 3am)
```

## Compaction Instructions

When compacting, always preserve:
1. Full list of modified files in this session
2. Current PM2 instance status (online/errored)
3. Which phases are complete vs pending
4. Any failing tests or errors found
5. Current git branch and last commit hash
