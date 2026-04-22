"""Basic syntax and safety validation for GenLayer contract code."""

import ast
import re


def validate_contract_code(code: str) -> tuple[bool, str]:
    """Validate contract code for syntax and basic safety.

    Returns:
        (is_valid, error_message) - error_message is empty if valid.
    """
    # Check for empty code
    if not code or not code.strip():
        return False, "Empty code provided."

    # Syntax check via AST parsing
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"

    # Safety checks
    dangerous_patterns = [
        (r"\beval\s*\(", "eval() is not allowed in contracts"),
        (r"\bexec\s*\(", "exec() is not allowed in contracts"),
        (r"\b__import__\s*\(", "Dynamic imports via __import__ are not allowed"),
        (r"\bsubprocess\b", "subprocess module is not allowed"),
        (r"\bos\.system\b", "os.system() is not allowed"),
        (r"\bos\.popen\b", "os.popen() is not allowed"),
        (r"\bshutil\b", "shutil module is not allowed"),
        (r"\bctypes\b", "ctypes module is not allowed"),
    ]

    for pattern, message in dangerous_patterns:
        if re.search(pattern, code):
            return False, f"Security violation: {message}"

    # Warn but allow if genlayer import is missing (might be implicit)
    # This is just a warning, not a hard failure
    if "genlayer" not in code and "gl." not in code:
        return False, (
            "This does not appear to be a GenLayer contract. "
            "Expected `from genlayer import *` or use of `gl.` primitives."
        )

    return True, ""
