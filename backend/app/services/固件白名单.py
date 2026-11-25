"""固件门禁：凭证表 + 只读归档。

工程形态（本仓选定）：
- 凭证表：白名单每次变更落一条「最低版本 + 指纹」史，指纹不可回刷（低版本设置被拒）；
- 双轨读引用：低版本报文只进 `固件归档`（只读），现行 `入栏缓冲` 只收达标固件集；
- 现行入栏每行带 `固件指纹`，低版本灌入后现行是否增行可区分（入栏不增、归档增）。

争用约束：装载批读完白名单快照后须在落库前重读一次（`_钩子` 为并发测试检查点），
快照指纹变化则整批按新白名单重评，避免「改白名单瞬间灌入」漏拦。
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.db import 连接

标题 = "固件门禁"
形态 = "凭证表+只读归档"
默认最低版本 = "1.2.0"
_钩子 = None  # 争用检查点：装载批读快照后、落库前触发；并发测试可注入


def _时刻() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS 固件白名单史("
        "编号 INTEGER PRIMARY KEY AUTOINCREMENT,"
        "指纹 TEXT NOT NULL UNIQUE,"
        "最低版本 TEXT NOT NULL,"
        "备注 TEXT NOT NULL DEFAULT '',"
        "时刻 TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS 探头固件("
        "站点键 TEXT PRIMARY KEY,"
        "固件版本 TEXT NOT NULL,"
        "登记时 TEXT NOT NULL)"
    )
    conn.execute(
        "CREATE TABLE IF NOT EXISTS 固件归档("
        "编号 INTEGER PRIMARY KEY AUTOINCREMENT,"
        "报文编号 TEXT NOT NULL,"
        "站点键 TEXT NOT NULL,"
        "指标键 TEXT NOT NULL,"
        "读数 REAL NOT NULL,"
        "观测时 TEXT NOT NULL,"
        "固件版本 TEXT NOT NULL,"
        "固件指纹 TEXT NOT NULL,"
        "原因 TEXT NOT NULL,"
        "入档时 TEXT NOT NULL)"
    )


def _元(v: str) -> tuple[int, ...] | None:
    parts = str(v or "").strip().split(".")
    if not parts or any(not p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts)


def 版本不低于(a: str, b: str) -> bool:
    """a >= b（点分整数版本）；格式不合法一律视为不达标。"""
    ma, mb = _元(a), _元(b)
    if ma is None or mb is None:
        return False
    n = max(len(ma), len(mb))
    return ma + (0,) * (n - len(ma)) >= mb + (0,) * (n - len(mb))


def _指纹(最低版本: str, 序号: int, 前置: str) -> str:
    raw = f"{最低版本}|{序号}|{前置}".encode("utf-8")
    return "fw-" + hashlib.sha256(raw).hexdigest()[:12]


def _史(conn) -> list[dict]:
    _ensure(conn)
    rows = conn.execute(
        "SELECT 编号,指纹,最低版本,备注,时刻 FROM 固件白名单史 ORDER BY 编号"
    ).fetchall()
    return [dict(r) for r in rows]


def _确保基线(conn, 提交: bool = True) -> None:
    """基线只在史为空时落一次。装载批在写事务内调用须 `提交=False`，不得提前放锁。"""
    _ensure(conn)
    if conn.execute("SELECT COUNT(*) AS c FROM 固件白名单史").fetchone()["c"]:
        return
    fp = _指纹(默认最低版本, 1, "base")
    conn.execute(
        "INSERT INTO 固件白名单史(指纹,最低版本,备注,时刻) VALUES (?,?,?,?)",
        (fp, 默认最低版本, "基线", _时刻()),
    )
    if 提交:
        conn.commit()


def _规则(conn, 提交: bool = True) -> dict:
    _确保基线(conn, 提交)
    史 = _史(conn)
    cur = 史[-1]
    return {
        "最低版本": cur["最低版本"],
        "指纹": cur["指纹"],
        "编号": cur["编号"],
        "史": 史,
    }


def 当前规则(conn=None, 提交: bool = True) -> dict:
    """读当前白名单。传入 conn 时复用同一事务，供装载批在写锁内取快照。"""
    if conn is not None:
        return _规则(conn, 提交)
    c = 连接()
    try:
        return _规则(c)
    finally:
        c.close()


def 设最低版本(版本: str, 备注: str = "") -> dict:
    """抬升最低版本→新指纹入史；低于当前→拒绝回刷，指纹不变。

    写事务抢 `BEGIN IMMEDIATE`：与装载批的读-判-落串行，切换瞬间不漏拦。
    指纹以 (最低版本, 序号, 前序指纹) 派生，序号 = 父编号 + 1，天然单调。
    """
    v = str(版本 or "").strip()
    if _元(v) is None:
        return {"错误": "版本格式不合法", "规则": 当前规则()}
    conn = 连接()
    try:
        conn.execute("BEGIN IMMEDIATE")
        确保基线 = _确保基线
        确保基线(conn, 提交=False)
        史 = _史(conn)
        cur = 史[-1]
        if not 版本不低于(v, cur["最低版本"]):
            conn.rollback()
            return {"错误": f"拒低版本回刷：{v} < {cur['最低版本']}", "规则": 当前规则()}
        if v == cur["最低版本"]:
            conn.rollback()
            return {"ok": True, "未变化": True, **_规则(conn, 提交=False)}
        fp = _指纹(v, cur["编号"] + 1, cur["指纹"])
        conn.execute(
            "INSERT INTO 固件白名单史(指纹,最低版本,备注,时刻) VALUES (?,?,?,?)",
            (fp, v, 备注 or "", _时刻()),
        )
        出 = _规则(conn, 提交=False)
        conn.commit()
        return {"ok": True, **出}
    finally:
        conn.close()


def 登记探头(站点键: str, 固件版本: str) -> dict:
    v = str(固件版本 or "").strip()
    if not str(站点键 or "").strip():
        return {"错误": "站点键为空"}
    if _元(v) is None:
        return {"错误": "版本格式不合法"}
    conn = 连接()
    try:
        _ensure(conn)
        conn.execute(
            "INSERT INTO 探头固件(站点键,固件版本,登记时) VALUES (?,?,?) "
            "ON CONFLICT(站点键) DO UPDATE SET 固件版本=excluded.固件版本, 登记时=excluded.登记时",
            (str(站点键), v, _时刻()),
        )
        conn.commit()
        return {"ok": True, "站点键": str(站点键), "固件版本": v}
    finally:
        conn.close()


def 登记探头表(conn=None) -> dict[str, str]:
    if conn is not None:
        _ensure(conn)
        return {
            r["站点键"]: r["固件版本"]
            for r in conn.execute("SELECT 站点键,固件版本 FROM 探头固件").fetchall()
        }
    c = 连接()
    try:
        return 登记探头表(c)
    finally:
        c.close()


def 有效固件(报文固件, 站点键: str, 登记: dict[str, str] | None = None) -> str:
    """报文自带固件优先；否则取站点源登记的探头痛固件。"""
    v = str(报文固件 or "").strip()
    if v:
        return v
    if 登记 is None:
        登记 = 登记探头表()
    return str(登记.get(站点键) or "")


def 判定(固件: str, 最低版本: str) -> tuple[str, str]:
    if not 固件:
        return "未署", "未署固件"
    if 版本不低于(固件, 最低版本):
        return "达标", "固件达标"
    return "低版本", f"固件低版本[{固件}<{最低版本}]"


def 归档列表(限制: int = 200) -> list[dict]:
    conn = 连接()
    try:
        _ensure(conn)
        rows = conn.execute(
            "SELECT * FROM 固件归档 ORDER BY 编号 DESC LIMIT ?", (限制,)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def _笔数(conn, sql: str, args: tuple = ()) -> int:
    return int(conn.execute(sql, args).fetchone()["c"])


def 对账() -> dict:
    """站点源对账：固件灯 + 现行入栏低版笔数；灯红且有入栏不得合法绿。"""
    规则 = 当前规则()
    最低 = 规则["最低版本"]
    conn = 连接()
    try:
        _ensure(conn)
        站点 = [dict(r) for r in conn.execute("SELECT 源键 FROM 站点源").fetchall()]
        登记 = {
            r["站点键"]: r["固件版本"]
            for r in conn.execute("SELECT 站点键,固件版本 FROM 探头固件").fetchall()
        }
        入栏 = conn.execute(
            "SELECT 站点键,固件版本,固件指纹 FROM 入栏缓冲"
        ).fetchall()
        归档 = conn.execute(
            "SELECT 站点键,固件版本,固件指纹 FROM 固件归档"
        ).fetchall()
        旁路 = conn.execute(
            "SELECT 站点键 FROM 观测报文 WHERE 命运='固件旁路'"
        ).fetchall()

        键集 = {s["源键"] for s in 站点} | set(登记) | {r["站点键"] for r in 入栏} | {
            r["站点键"] for r in 归档
        }
        明细 = []
        灯: dict[str, str] = {}
        低版行 = 0
        红站有入栏 = False
        for k in sorted(键集):
            reg = str(登记.get(k) or "")
            行 = [r for r in 入栏 if r["站点键"] == k]
            行低 = [
                r for r in 行
                if r["固件版本"] and not 版本不低于(r["固件版本"], 最低)
            ]
            行未署 = [r for r in 行 if not r["固件版本"]]
            红 = bool(reg) and not 版本不低于(reg, 最低)
            红 = 红 or bool(行低)
            灯[k] = "红" if 红 else "绿"
            if 红 and 行:
                红站有入栏 = True
            低版行 += len(行低)
            明细.append({
                "站点键": k,
                "登记固件": reg,
                "灯": 灯[k],
                "入栏笔数": len(行),
                "低版入栏笔数": len(行低),
                "未署入栏笔数": len(行未署),
                "归档笔数": sum(1 for r in 归档 if r["站点键"] == k),
                "拦截笔数": sum(1 for r in 旁路 if r["站点键"] == k),
            })
        红站 = [k for k, v in 灯.items() if v == "红"]
        有入栏 = 低版行 > 0 or 红站有入栏
        状态 = "绿" if not 红站 else ("红-有入栏漏检" if 有入栏 else "红-无入栏")
        return {
            "最低版本": 最低,
            "指纹": 规则["指纹"],
            "灯": 灯,
            "明细": 明细,
            "红站": 红站,
            "现行入栏低版行": 低版行,
            "现行入栏笔数": len(入栏),
            "有入栏": 有入栏,
            "归档笔数": len(归档),
            "状态": 状态,
            "合法绿": not 红站 and 低版行 == 0,
        }
    finally:
        conn.close()


def 站点源对账() -> dict:
    """站点源页专用：逐站点灯 + 门禁摘要，避免页面二次拼装。"""
    账 = 对账()
    板 = 门禁看板()
    return {
        "最低版本": 账["最低版本"],
        "指纹": 账["指纹"],
        "状态": 账["状态"],
        "合法绿": 账["合法绿"],
        "灯": 账["灯"],
        "明细": 账["明细"],
        "拦截笔数": 板["拦截笔数"],
        "归档笔数": 账["归档笔数"],
        "现行入栏笔数": 账["现行入栏笔数"],
        "现行入栏低版行": 账["现行入栏低版行"],
        "形态": 板["形态"],
    }


def 门禁看板() -> dict:
    规则 = 当前规则()
    账 = 对账()
    conn = 连接()
    try:
        _ensure(conn)
        拦截 = _笔数(
            conn, "SELECT COUNT(*) AS c FROM 观测报文 WHERE 命运='固件旁路'"
        )
        达标入栏 = _笔数(
            conn,
            "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 固件版本<>'' AND 固件指纹<>''",
        )
        未署入栏 = _笔数(
            conn, "SELECT COUNT(*) AS c FROM 入栏缓冲 WHERE 固件版本=''"
        )
        归档 = _笔数(conn, "SELECT COUNT(*) AS c FROM 固件归档")
    finally:
        conn.close()
    return {
        "标题": 标题,
        "形态": 形态,
        "最低版本": 规则["最低版本"],
        "指纹": 规则["指纹"],
        "史": 规则["史"],
        "探头": 登记探头表(),
        "对账": 账,
        "拦截笔数": 拦截,
        "达标入栏笔数": 达标入栏,
        "未署入栏笔数": 未署入栏,
        "归档笔数": 归档,
        "读引用": {"现行入栏": "达标固件集", "低版本": "只读归档"},
    }
