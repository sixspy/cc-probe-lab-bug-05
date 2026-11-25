"""固件白名单双写两轨：低版本只读归档 + 现行达标入栏。

双写读引用不同：
- 现行入栏只读达标固件集（`live_flag`）；
- 低版本报文进只读归档（`archive_*`），不参与汇总。

不再只亮镜像芯片；`dual_board()` 返回的两轨均为真实表。
"""
from __future__ import annotations

from app.services import fwgate as core
from app.services import 固件白名单

_SLUG = "fwgate"
_TITLE = "固件白名单"
_OK = "固件已亮"


def apply_dualwrite(note: str = "") -> dict:
    """双写无需造数：归档与现行两轨由装载自然产生；此处只回真实两轨读数。"""
    板 = 固件白名单.门禁看板()
    return {
        "dual_chip": _OK if 板["对账"]["合法绿"] else "固件灯红",
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "archive_count": 板["归档笔数"],
        "live_flag": core.live_flag(),
        "note": note or _TITLE,
        "读引用": 板["读引用"],
    }


def dual_board() -> dict:
    dash = core.dashboard()
    return {
        "dual_chip": core.panel_chip(),
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "archive": core.archive_rows(),
        "live_flag": core.live_flag(),
        "dash": dash,
        "fate": "dualwrite",
        "panel_pack_mismatch": not dash["合法绿"],
        "title": f"{_TITLE}双写面",
    }


def apply_dualwrite_action(note: str = "") -> dict:
    板 = 固件白名单.门禁看板()
    return {**apply_dualwrite(note), "看板": 板}
