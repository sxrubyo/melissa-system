"""melissa_weekly_report.py — Weekly brain report to admin."""
from __future__ import annotations
import json, logging, sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger("melissa.weekly_report")


async def generate_weekly_report(instance_id: str, db_path: str = "melissa.db") -> str:
    """Generate a human-readable weekly report."""
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        week_ago = (datetime.now() - timedelta(days=7)).isoformat()

        # Count conversations
        c.execute("SELECT COUNT(DISTINCT chat_id) as patients FROM conversations WHERE role='user' AND created_at > ?", (week_ago,))
        row = c.fetchone()
        total_patients = row["patients"] if row else 0

        # Count messages
        c.execute("SELECT COUNT(*) as msgs FROM conversations WHERE created_at > ?", (week_ago,))
        row = c.fetchone()
        total_msgs = row["msgs"] if row else 0

        # Count gaps
        gaps_dir = Path("knowledge_gaps")
        gaps_count = 0
        gap_questions = []
        if gaps_dir.exists():
            for f in gaps_dir.glob("*.jsonl"):
                for line in open(f):
                    try:
                        g = json.loads(line)
                        gaps_count += 1
                        gap_questions.append(g.get("user_msg", "")[:80])
                    except:
                        pass

        # Count teachings learned
        teachings_file = Path(f"teachings/{instance_id}.jsonl")
        teachings_this_week = 0
        if teachings_file.exists():
            for line in open(teachings_file):
                try:
                    t = json.loads(line)
                    if t.get("ts", "") > week_ago:
                        teachings_this_week += 1
                except:
                    pass

        conn.close()

        # Build report
        report = (
            f"hola! te cuento cómo me fue esta semana:\n\n"
            f"hablé con {total_patients} pacientes ({total_msgs} mensajes)\n"
            f"aprendí {teachings_this_week} cosas nuevas\n"
        )

        if gaps_count > 0:
            report += f"\nhubo {gaps_count} preguntas que no supe responder:\n"
            for q in gap_questions[:5]:
                report += f"  • {q}\n"
            report += "\nsi me enseñas con /aprender las respondo sola la próxima vez"
        else:
            report += "\nrespondí todo sin problemas esta semana 💪"

        return report

    except Exception as e:
        log.error(f"[weekly_report] error: {e}")
        return "no pude generar el reporte esta semana, perdona"


async def send_weekly_report(instance_id: str, admin_jid: str, send_fn, db_path: str = "melissa.db"):
    """Generate and send weekly report to admin."""
    report = await generate_weekly_report(instance_id, db_path)
    if send_fn and report:
        await send_fn(admin_jid, report)
        log.info(f"[weekly_report] sent to {admin_jid}")
