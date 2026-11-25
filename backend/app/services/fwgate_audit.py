"""固件白名单读轨审计。"""
from __future__ import annotations

from app.services import fwgate as core
from app.services import fwgate_cutover as cutover
from app.services import fwgate_dualwrite as dual


def audit_summary() -> dict:
    return {
        "title": "固件白名单审计",
        "core": core.dashboard(),
        "cutover": cutover.board(),
        "dualwrite": dual.dual_board(),
        "half": core.half_fix_display(),
    }
