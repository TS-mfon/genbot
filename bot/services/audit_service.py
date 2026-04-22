"""AI audit service using Claude API."""

import logging

from bot.config import settings

logger = logging.getLogger(__name__)

AUDIT_PROMPT = """You are an expert auditor for GenLayer Intelligent Contracts.
GenLayer contracts are Python classes that use `from genlayer import *` and can include
non-deterministic operations via EquivalencePrinciple for validator consensus.

Analyze the following contract code and provide:

1. **Security Issues** - vulnerabilities, reentrancy risks, access control problems
2. **Best Practices** - coding standards, proper use of GenLayer primitives
3. **Gas/Efficiency** - any performance concerns
4. **Logic Errors** - potential bugs or edge cases
5. **Recommendations** - specific improvements

Rate the overall security: SAFE / CAUTION / UNSAFE

Contract code:
```python
{code}
```

Provide a clear, structured audit report."""


class AuditService:
    """Contract auditing via Claude API."""

    async def audit_contract(self, code: str) -> str:
        """Audit a GenLayer contract using Claude."""
        if not settings.anthropic_api_key:
            return self._basic_audit(code)

        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            message = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": AUDIT_PROMPT.format(code=code),
                    }
                ],
            )
            return message.content[0].text
        except ImportError:
            logger.warning("anthropic package not installed, using basic audit")
            return self._basic_audit(code)
        except Exception as e:
            logger.error(f"Claude audit failed: {e}")
            return self._basic_audit(code)

    def _basic_audit(self, code: str) -> str:
        """Perform a basic static audit without AI."""
        issues = []
        warnings = []
        info = []

        if "from genlayer import" not in code:
            issues.append("Missing `from genlayer import *` - not a valid GenLayer contract.")

        if "eval(" in code or "exec(" in code:
            issues.append("CRITICAL: Use of eval()/exec() detected - potential code injection.")

        if "__import__" in code:
            issues.append("WARNING: Dynamic imports detected via __import__.")

        if "os." in code or "import os" in code:
            warnings.append("Use of `os` module detected - may not be available in GenLayer runtime.")

        if "subprocess" in code:
            issues.append("CRITICAL: subprocess usage detected - not allowed in contracts.")

        if "open(" in code:
            warnings.append("File I/O detected - not available in GenLayer runtime.")

        if "@public" not in code and "def " in code:
            info.append("No @public decorator found - ensure methods are properly exposed.")

        if "EquivalencePrinciple" in code:
            info.append("Uses EquivalencePrinciple for non-deterministic consensus.")

        if "__init__" not in code:
            info.append("No __init__ constructor found.")

        report = "=== Basic Contract Audit ===\n\n"

        if issues:
            report += "ISSUES:\n" + "\n".join(f"  [!] {i}" for i in issues) + "\n\n"
        if warnings:
            report += "WARNINGS:\n" + "\n".join(f"  [~] {w}" for w in warnings) + "\n\n"
        if info:
            report += "INFO:\n" + "\n".join(f"  [i] {n}" for n in info) + "\n\n"

        if not issues:
            report += "Rating: SAFE (basic check only - consider setting ANTHROPIC_API_KEY for full AI audit)\n"
        elif any("CRITICAL" in i for i in issues):
            report += "Rating: UNSAFE\n"
        else:
            report += "Rating: CAUTION\n"

        return report


# Singleton
audit_service = AuditService()
