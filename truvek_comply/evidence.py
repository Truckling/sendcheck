import hashlib, json, os, uuid
from datetime import datetime, timezone
from pathlib import Path
from .rules import RULESET_VERSION


def _log_path() -> Path:
    p = Path(os.environ.get("SENDCHECK_LOG", str(Path.home() / ".sendcheck" / "evidence.jsonl")))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def record_check(subject: str, body: str, recipient: str, result: dict, campaign_id: str = "") -> str:
    """Write one line to the evidence log. Returns check_id."""
    check_id = str(uuid.uuid4())
    content_hash = hashlib.sha256(f"{subject}\n{body}\n{recipient}".encode()).hexdigest()
    entry = {
        "check_id": check_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "content_hash": content_hash,
        "verdict": result["verdict"],
        "rule_ids": [f["rule_id"] for f in result.get("findings", [])],
        "ruleset_version": RULESET_VERSION,
        "campaign_id": campaign_id or None,
    }
    with open(_log_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")
    return check_id


def get_evidence(check_id: str = "", campaign_id: str = "", limit: int = 20) -> list[dict]:
    """Return log entries matching check_id or campaign_id. Returns recent entries if neither given."""
    path = _log_path()
    if not path.exists():
        return []
    results = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if check_id and entry.get("check_id") == check_id:
                results.append(entry)
            elif campaign_id and entry.get("campaign_id") == campaign_id:
                results.append(entry)
            elif not check_id and not campaign_id:
                results.append(entry)
    return results[-limit:]
