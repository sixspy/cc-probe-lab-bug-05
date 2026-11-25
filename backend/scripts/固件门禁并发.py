"""固件门禁并发争用脚本：改白名单瞬间并发灌入，核验不漏拦。

用法（仓根）：
    python3 backend/scripts/固件门禁并发.py [--线程 4] [--每线程 8]

判据（任一不满足即退出码 1）：
- 现行入栏每行固件 >= 该行指纹对应白名单的最低版本；
- 入栏 + 只读归档 = 总灌入笔数（去向可区分）；
- 归档行固件均低于其指纹对应最低版本。
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import threading
from pathlib import Path

_HERE = Path(__file__).resolve()
_BACKEND = _HERE.parents[1]
sys.path.insert(0, str(_BACKEND))


def main() -> int:
    解 = argparse.ArgumentParser()
    解.add_argument("--线程", type=int, default=4)
    解.add_argument("--每线程", type=int, default=8)
    参数 = 解.parse_args()

    if not os.environ.get("数据目录"):
        os.environ["数据目录"] = tempfile.mkdtemp(prefix="fwgate-")
    os.environ.setdefault("夹具目录", str(_BACKEND.parent / "fixtures"))

    from app import seed
    from app.services import 装载, 目录, 固件白名单

    seed.初始化库()
    固件白名单.设最低版本("1.5.0", "并发脚本基线")

    结果: list[dict] = []
    错: list[BaseException] = []

    def 灌(i: int) -> None:
        try:
            for j in range(参数.每线程):
                版本 = "1.4.0" if j % 2 == 0 else "1.7.0"
                结果.append(装载.装一批({
                    "批次编号": f"并发脚本-{i}-{j}",
                    "报文": [{
                        "报文编号": f"FW-S-{i}-{j}",
                        "站点键": "站-河东",
                        "指标键": "PM25",
                        "读数": 20.0 + i,
                        "观测时": f"2026-11-24T14:{i:02d}:{j:02d}Z",
                        "固件版本": 版本,
                    }],
                }))
        except BaseException as exc:  # noqa: BLE001
            错.append(exc)

    def 抬升() -> None:
        try:
            固件白名单.设最低版本("1.5.5", "并发脚本抬升")
            固件白名单.设最低版本("1.6.0", "并发脚本再抬升")
            # 低版本回刷应被拒，指纹不得回退
            if "错误" not in 固件白名单.设最低版本("1.0.0", "回刷尝试"):
                错.append(AssertionError("低版本回刷未被拒"))
        except BaseException as exc:  # noqa: BLE001
            错.append(exc)

    线程 = [threading.Thread(target=灌, args=(i,)) for i in range(参数.线程)]
    线程.append(threading.Thread(target=抬升))
    for t in 线程:
        t.start()
    for t in 线程:
        t.join(60)

    总 = 参数.线程 * 参数.每线程
    if 错:
        print(f"[红] 并发执行异常：{错!r}")
        return 1
    if len(结果) != 总:
        print(f"[红] 批次缺失：期望 {总} 实得 {len(结果)}")
        return 1

    史 = {h["指纹"]: h["最低版本"] for h in 固件白名单.当前规则()["史"]}
    入栏 = 目录.缓冲列表()
    归档 = 目录.固件归档列表()
    失败: list[str] = []
    for r in 入栏:
        最低 = 史.get(r["固件指纹"])
        if 最低 is None:
            失败.append(f"{r['报文编号']} 指纹不可回溯 {r['固件指纹']}")
        elif not 固件白名单.版本不低于(r["固件版本"], 最低):
            失败.append(
                f"{r['报文编号']} 固件 {r['固件版本']} 低于指纹 {r['固件指纹']} 的 {最低}"
            )
    for r in 归档:
        最低 = 史.get(r["固件指纹"])
        if 最低 is None:
            失败.append(f"{r['报文编号']} 归档指纹不可回溯")
        elif 固件白名单.版本不低于(r["固件版本"], 最低):
            失败.append(f"{r['报文编号']} 归档行并非低版本")
    if len(入栏) + len(归档) != 总:
        失败.append(f"去向缺口：入栏 {len(入栏)} + 归档 {len(归档)} != {总}")

    账 = 固件白名单.对账()
    if not 账["合法绿"]:
        失败.append(f"对账未合法绿：{账['状态']}（漏检 {账['现行入栏低版行']}）")

    print(f"灌入批次 {len(结果)} · 现行入栏 {len(入栏)} · 只读归档 {len(归档)} · 对账 {账['状态']}")
    for h in 固件白名单.当前规则()["史"]:
        print(f"  指纹 {h['指纹']} 最低 {h['最低版本']} 备注 {h['备注']}")
    if 失败:
        print("[红] 争用漏拦：")
        for f in 失败:
            print("  -", f)
        return 1
    print("[绿] 白名单切换瞬间无漏拦，去向可区分。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
