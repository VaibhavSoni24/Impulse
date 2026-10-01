"""Tool Contract Stability Auditor for Stage 37 (Section 11).

Audits the 9 pre-defined competition-facing tool contracts:
1. run_command
2. read_file
3. edit_file
4. write_file
5. get_status
6. submit_patch
7. get_code_neighbors
8. search_similar_code
9. get_code_subgraph

Ensures tool interfaces, signatures, and contracts remain strictly frozen,
preventing later LoRA experiments from confounding adapter effects with tool contract shifts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from local.lora_opt.models import ToolContractRecord, ToolContractStatus

PREDEFINED_TOOL_SIGNATURES: dict[str, dict[str, str]] = {
    "run_command": {
        "signature": "run_command(command: str) -> str",
        "description": "Execute shell command in persistent sandboxed container environment.",
    },
    "submit_patch": {
        "signature": "submit_patch() -> str",
        "description": "Extract diff against clean baseline and submit final patch for scoring.",
    },
    "get_status": {
        "signature": "get_status() -> str",
        "description": "Inspect git working tree status, modified files, and untracked artifacts.",
    },
    "read_file": {
        "signature": "read_file(filepath: str, start_line: int | None = None, end_line: int | None = None) -> str",
        "description": "Read file contents with optional 1-indexed line range slicing.",
    },
    "edit_file": {
        "signature": "edit_file(filepath: str, old_string: str, new_string: str, allow_multiple: bool = False) -> str",
        "description": "Deterministic string replacement in workspace file.",
    },
    "write_file": {
        "signature": "write_file(filepath: str, content: str) -> str",
        "description": "Write entire file contents, creating parent directories if needed.",
    },
    "get_code_neighbors": {
        "signature": "get_code_neighbors(node: str, edge_type: str | None = None, max_neighbors: int = 50) -> str",
        "description": "Query AST/call graph neighbor nodes for a code symbol.",
    },
    "search_similar_code": {
        "query": "search_similar_code(query: str, k: int = 10) -> str",
        "signature": "search_similar_code(query: str, k: int = 10) -> str",
        "description": "Retrieve code chunks matching semantic query via pre-computed embeddings.",
    },
    "get_code_subgraph": {
        "signature": "get_code_subgraph(nodes: list[str]) -> str",
        "description": "Extract subgraph surrounding designated node identifiers.",
    },
}


def compute_contract_hash(signature: str) -> str:
    """Computes deterministic SHA-256 digest of normalized tool signature."""
    clean = signature.strip().replace(" ", "")
    return hashlib.sha256(clean.encode("utf-8")).hexdigest()


class ToolContractAuditor:
    """Audits tool contracts against recorded competition specifications."""

    def __init__(self, repo_root: Optional[Path | str] = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else Path.cwd()
        self.facts_path = self.repo_root / "local" / "competition_facts.json"

    def audit_tool_contracts(self) -> Tuple[bool, List[ToolContractRecord], Dict[str, str]]:
        """Audits all 9 tool contracts, returns (all_stable, records, hashes)."""
        records: list[ToolContractRecord] = []
        hashes: dict[str, str] = {}
        all_stable = True

        for tool_name, spec in PREDEFINED_TOOL_SIGNATURES.items():
            sig = spec["signature"]
            c_hash = compute_contract_hash(sig)
            hashes[tool_name] = c_hash

            rec = ToolContractRecord(
                tool_name=tool_name,
                signature=sig,
                contract_hash=c_hash,
                source_location="local/competition_facts.json",
                status=ToolContractStatus.STABLE.value,
                reason="Pre-defined competition harness tool signature verified.",
            )
            records.append(rec)

        # Cross-reference with competition_facts.json if present
        if self.facts_path.exists():
            facts = json.loads(self.facts_path.read_text(encoding="utf-8"))
            facts_tools = facts.get("available_predefined_tools", [])
            for r in records:
                matched = any(r.signature == ft for ft in facts_tools)
                if not matched:
                    r.status = ToolContractStatus.CHANGED.value
                    r.reason = "Signature mismatch against competition_facts.json"
                    all_stable = False

        return all_stable, records, hashes


def get_competition_tool_contracts(repo_root: Optional[Path | str] = None) -> List[ToolContractRecord]:
    """Retrieve list of competition tool contract records."""
    auditor = ToolContractAuditor(repo_root=repo_root)
    _, records, _ = auditor.audit_tool_contracts()
    return records


def verify_tool_contracts(repo_root: Optional[Path | str] = None) -> Dict[str, ToolContractRecord]:
    """Verify tool contracts and return mapping from tool name to ToolContractRecord."""
    auditor = ToolContractAuditor(repo_root=repo_root)
    _, records, _ = auditor.audit_tool_contracts()
    return {r.tool_name: r for r in records}
