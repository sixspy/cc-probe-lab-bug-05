"""固件白名单切流账册：锁指纹拒回刷（凭证表读引用）。

本仓选定工程形态为「凭证表 + 只读归档」：
- 切流 = 现行读引用锁在凭证指纹上（`cutover_book`），白名单只可抬升，低版本设置被拒；
- 不再有只写软笔记、灯绿即算数的假面；返回值全部读真实门禁账。
"""
from __future__ import annotations

from app.services import fwgate as core
from app.services import 固件白名单

_SLUG = "fwgate"
_TITLE = "固件白名单"
_OK = "固件已亮"


def append_cutover(ref_id: int, note: str = "") -> dict:
    """切流登记：只落备注，读引用始终由凭证指纹决定，不接受弱化。"""
    out = {
        "ref_id": ref_id,
        "note": note,
        "panel": core.panel_chip(),
        "truth": core.truth_flag(),
        "active_read": core.active_read_ref(),
        "cutover_fp": core.cutover_fp(),
        "reject_refresh": core.reject_refresh(),
        "最低版本": 固件白名单.当前规则()["最低版本"],
    }
    out["panel_pack_mismatch"] = not out["reject_refresh"]
    return out


def board() -> dict:
    dash = core.dashboard()
    dash["fate"] = "cutover_book"
    dash["read_ref"] = core.active_read_ref()
    return dash


def apply_cutover(最低版本: str, 备注: str = "") -> dict:
    """切流动作：抬升最低版本（低版本回刷被拒），回真实对账。"""
    设 = 固件白名单.设最低版本(最低版本, 备注)
    return {"设最低版本": 设, "看板": board()}
