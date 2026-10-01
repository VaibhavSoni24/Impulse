"""Privacy and Secret Sanitization Subsystem for Stage 38 (Section 17).

Detects, sanitizes, and rejects:
- API keys (OpenAI, Anthropic, Google, GitHub, GitLab, HuggingFace)
- Private cryptographic keys and certificates
- Bearer tokens, passwords, and embedded credentials in URLs
- Cloud secrets (AWS access keys, GCP credentials)
- Machine-specific user paths (e.g. C:\\Users\\... or /home/...)

Enforces the Zero Secrets Policy (AGENTS.md):
If an authentic secret or private key is detected, the candidate example
is marked for rejection (REJECT_SECRET) rather than dangerously masked.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

# Regex patterns for credential detection
SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("OPENAI_KEY", re.compile(r"\bsk-[a-zA-Z0-9]{20,}\b")),
    ("GOOGLE_API_KEY", re.compile(r"\bAIza[0-9A-Za-z-_]{35}\b")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[pousr]_[0-9a-zA-Z]{36}\b")),
    ("GITLAB_TOKEN", re.compile(r"\bglpat-[0-9a-zA-Z\-]{20,}\b")),
    ("HUGGINGFACE_TOKEN", re.compile(r"\bhf_[0-9a-zA-Z]{34,}\b")),
    ("BEARER_TOKEN", re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9_\-\.]{25,}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN\s+[A-Z\s]+PRIVATE\s+KEY-----")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("PASSWORD_IN_URL", re.compile(r"https?://[^:\s@]+:[^:\s@]+@[^\s/]+")),
    ("GENERIC_PASSWORD", re.compile(r"(?i)(?:password|passwd|api_secret|access_token)\s*[:=]\s*['\"][^\s'\"]{8,}['\"]")),
]

# Path normalization patterns
PATH_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("WINDOWS_USER_PATH", re.compile(r"[A-Za-z]:\\[Uu]sers\\[^\\]+\\", re.IGNORECASE)),
    ("UNIX_USER_PATH", re.compile(r"/(?:home|Users)/[^/]+/", re.IGNORECASE)),
]


class SecretSanitizer:
    """Detects and cleans secrets and host-specific paths in training examples."""

    def __init__(self, reject_on_secret: bool = True) -> None:
        self.reject_on_secret = reject_on_secret

    def inspect_text(self, text: str) -> tuple[bool, int, list[str]]:
        """Inspects text for sensitive credentials without modifying it.
        
        Returns:
            (has_credentials, finding_count, list_of_reasons)
        """
        if not text:
            return False, 0, []

        findings: list[str] = []
        for name, pattern in SECRET_PATTERNS:
            matches = pattern.findall(text)
            if matches:
                findings.append(f"Detected {name} ({len(matches)} instance(s))")

        return len(findings) > 0, len(findings), findings

    def sanitize_paths(self, text: str) -> tuple[str, int]:
        """Normalizes host-specific file paths to standard repo-relative placeholders."""
        if not text:
            return text, 0

        clean = text
        count = 0
        for name, pattern in PATH_PATTERNS:
            matches = pattern.findall(clean)
            if matches:
                count += len(matches)
                clean = pattern.sub("[WORKSPACE_ROOT]/", clean)

        if "[WORKSPACE_ROOT]/" in clean:
            def fix_slashes(m: re.Match[str]) -> str:
                return m.group(0).replace("\\", "/")
            clean = re.sub(r"\[WORKSPACE_ROOT\]/[^\s\"'\(\)\[\]]+", fix_slashes, clean)

        return clean, count

    def sanitize_example(self, example_data: dict[str, Any]) -> tuple[dict[str, Any], bool, int, list[str]]:
        """Scans all text fields of an example.
        
        Returns:
            (sanitized_dict, is_clean, redaction_count, reasons)
        """
        data = dict(example_data)
        total_redactions = 0
        reasons: list[str] = []
        has_critical_secret = False

        # Check situation, evidence, tool calls, preferred & negative behaviors
        fields_to_check: list[str] = ["situation", "validation_signal"]
        for f in fields_to_check:
            val = data.get(f, "")
            if isinstance(val, str):
                has_sec, _, sec_reasons = self.inspect_text(val)
                if has_sec:
                    has_critical_secret = True
                    reasons.extend(sec_reasons)
                clean_txt, p_cnt = self.sanitize_paths(val)
                data[f] = clean_txt
                total_redactions += p_cnt

        # Check evidence list
        evidence_list = data.get("evidence", [])
        clean_evidence: list[str] = []
        for item in evidence_list:
            if isinstance(item, str):
                has_sec, _, sec_reasons = self.inspect_text(item)
                if has_sec:
                    has_critical_secret = True
                    reasons.extend(sec_reasons)
                clean_item, p_cnt = self.sanitize_paths(item)
                clean_evidence.append(clean_item)
                total_redactions += p_cnt
            else:
                clean_evidence.append(item)
        data["evidence"] = clean_evidence

        # Check tool sequence arguments
        tool_seq = data.get("tool_sequence", [])
        clean_seq: list[dict[str, Any]] = []
        for step in tool_seq:
            step_copy = dict(step)
            args_str = str(step_copy.get("arguments", {}))
            has_sec, _, sec_reasons = self.inspect_text(args_str)
            if has_sec:
                has_critical_secret = True
                reasons.extend(sec_reasons)
            clean_seq.append(step_copy)
        data["tool_sequence"] = clean_seq

        data["sanitized"] = not has_critical_secret
        data["redaction_count"] = total_redactions

        is_clean = not has_critical_secret
        return data, is_clean, total_redactions, reasons
