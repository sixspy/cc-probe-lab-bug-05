"""固件白名单收口面：页灯读真实门禁账，不再只亮不核。

工程形态：凭证表 + 只读归档。
- `固件白名单.门禁看板()` 是唯一真相源；
- 页灯 `panel_chip`/`truth` 均由现行入栏与对账实算，假绿不再可画；
- `cutover_book` 与 `live_flag` 两种读引用映射到真实表：
  `cutover_book` = 凭证指纹锁定（拒回刷生效），`live_flag` = 只读归档在轨。
"""
from __future__ import annotations

from app.services import 固件白名单

_SLUG = "fwgate"
_OK = "固件已亮"
_BAD = "低版本仍入"
_TITLE = "固件白名单"
_CUTOVER = "cutover_book"
_LIVE = "live_flag"


def _board() -> dict:
    return 固件白名单.门禁看板()


def panel_chip() -> str:
    板 = _board()
    账 = 板["对账"]
    return _OK if 账["合法绿"] else "固件灯红"


def truth_flag() -> str:
    账 = _board()["对账"]
    if 账["现行入栏低版行"]:
        return _BAD
    return "低版本已拦"


def active_read_ref() -> str:
    """达标入栏现行读 `live_flag`（只读归档在轨）；无入栏时读凭证 `cutover_book`。"""
    板 = _board()
    return _LIVE if 板["达标入栏笔数"] else _CUTOVER


def cutover_fp() -> str:
    return 固件白名单.当前规则()["指纹"]


def reject_refresh() -> bool:
    """拒低版本回刷已生效的判据：尝试回刷不应改变指纹。"""
    规则 = 固件白名单.当前规则()
    史 = 规则["史"]
    return len(史) >= 1 and all(
        not 固件白名单.版本不低于(b["最低版本"], a["最低版本"])
        for a, b in zip(史, 史[1:])
    )


def live_flag() -> str:
    return "达标入栏" if _board()["达标入栏笔数"] else ""


def archive_rows() -> list[dict]:
    return 固件白名单.归档列表()


def paint_ok() -> str:
    """保留旧调用名：不再无条件亮灯，回真实面板芯片。"""
    return panel_chip()


def commit_action(payload: dict | None = None) -> dict:
    """动作落点：把载荷里的最低版本/探头登记写进凭证表，回真实看板。"""
    payload = payload or {}
    out: dict = {"ok": True, "title": _TITLE}
    if payload.get("最低版本"):
        设 = 固件白名单.设最低版本(str(payload["最低版本"]), str(payload.get("备注") or ""))
        out["设最低版本"] = 设
        if "错误" in 设:
            out["ok"] = False
    for 项 in payload.get("探头") or []:
        if isinstance(项, dict) and 项.get("站点键"):
            out.setdefault("探头", []).append(
                固件白名单.登记探头(str(项["站点键"]), str(项.get("固件版本") or ""))
            )
    out["看板"] = dashboard()
    return out


def half_fix_display() -> dict:
    """半修演示：只改灯不改装载联查，真实对账仍报红。"""
    账 = _board()["对账"]
    return {
        "panel_chip": panel_chip(),
        "truth": truth_flag(),
        "active_read": active_read_ref(),
        "archive_count": len(archive_rows()),
        "对账状态": 账["状态"],
        "合法绿": 账["合法绿"],
        "half_fixed": 账["合法绿"],
    }


def snapshot() -> dict:
    板 = _board()
    账 = 板["对账"]
    return {
        "title": _TITLE,
        "形态": 板["形态"],
        "panel_chip": panel_chip(),
        "truth": truth_flag(),
        "active_read": active_read_ref(),
        "cutover_fp": cutover_fp(),
        "reject_refresh": reject_refresh(),
        "archive_count": 板["归档笔数"],
        "live_flag": live_flag(),
        "最低版本": 板["最低版本"],
        "对账状态": 账["状态"],
        "合法绿": 账["合法绿"],
        "aligned": 账["合法绿"],
        "panel_pack_mismatch": not 账["合法绿"],
        "gate_bypass": False,
    }


def dashboard() -> dict:
    snap = snapshot()
    return {
        **snap,
        "ok_chip": _OK,
        "bad_chip": _BAD,
        "label": _TITLE,
        "read_tracks": {"cutover_book": _CUTOVER, "live_flag": _LIVE},
        "门禁": _board(),
    }


def reconcile_display() -> dict:
    return half_fix_display()
