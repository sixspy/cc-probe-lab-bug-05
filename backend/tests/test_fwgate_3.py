"""争用失败测：改白名单瞬间灌入并发漏拦则红。

约束：
- 白名单变更与装载并发时，批次须按提交时的白名单重评，不得沿用旧快照漏拦；
- 现行入栏每行须带白名单指纹，指纹可回溯到当时的规则版本；
- 并发灌入后任何入栏行都不得低于其指纹对应规则的最低版本。
"""
import threading
import time
from app.services import 装载, 目录, 固件白名单


def _批(前缀: str, 版本: str, 站点: str = "站-河东") -> dict:
    return {
        "批次编号": "夹具-固件争用-" + 前缀,
        "报文": [{
            "报文编号": f"{前缀}-{版本}",
            "站点键": 站点,
            "指标键": "PM25",
            "读数": 20.0,
            "观测时": "2026-11-24T12:00:00Z",
            "固件版本": 版本,
        }],
    }


def test_白名单切换瞬间批次须重评(monkeypatch):
    assert 固件白名单.设最低版本("1.5.0", "基线")["最低版本"] == "1.5.0"
    已跑 = []

    def 钩():
        if 已跑:
            return
        已跑.append(1)
        # 装载批读快照后、落库前，白名单被并发抬到 1.6.0
        固件白名单.设最低版本("1.6.0", "争用抬升")

    monkeypatch.setattr(固件白名单, "_钩子", 钩)
    报告 = 装载.装一批(_批("FW-C-race", "1.4.0"))
    assert 已跑 == [1], "争用检查点未被装载批触发"
    assert 报告["固件重评"] == 1, "白名单已切换却未重评"
    assert 报告["入栏"] == 0, "白名单抬升后低版本仍入栏"
    assert 报告["归档"] == 1
    assert 目录.缓冲列表() == [], "争用瞬间漏拦：低版本进入现行入栏"


def test_无争用时高版本正常入栏(monkeypatch):
    monkeypatch.setattr(固件白名单, "_钩子", None)
    报告 = 装载.装一批(_批("FW-C-pass", "1.5.1"))
    assert 报告["入栏"] == 1
    assert 报告["固件重评"] == 0
    assert 报告["归档"] == 0


def test_并发灌入不漏拦():
    固件白名单.设最低版本("1.5.0", "并发基线")
    结果: list[dict] = []
    错: list[BaseException] = []

    def 灌(i: int) -> None:
        try:
            for j in range(5):
                结果.append(装载.装一批({
                    "批次编号": f"并发-{i}-{j}",
                    "报文": [{
                        "报文编号": f"FW-C-{i}-{j}",
                        "站点键": "站-河东",
                        "指标键": "PM25",
                        "读数": 20.0 + i,
                        "观测时": f"2026-11-24T12:{i:02d}:{j:02d}Z",
                        "固件版本": "1.6.0",
                    }],
                }))
        except BaseException as e:  # noqa: BLE001
            错.append(e)

    def 抬升() -> None:
        try:
            time.sleep(0.02)
            固件白名单.设最低版本("1.7.0", "并发抬升")
        except BaseException as e:  # noqa: BLE001
            错.append(e)

    线程 = [threading.Thread(target=灌, args=(i,)) for i in range(3)]
    线程.append(threading.Thread(target=抬升))
    for t in 线程:
        t.start()
    for t in 线程:
        t.join(20)
    assert not 错, f"并发执行异常：{错!r}"
    assert len(结果) == 15

    史 = {h["指纹"]: h["最低版本"] for h in 固件白名单.当前规则()["史"]}
    assert 史
    入栏 = 目录.缓冲列表()
    归档 = 目录.固件归档列表()
    for r in 入栏:
        assert r["固件指纹"] in 史, "入栏行指纹不可回溯"
        assert 固件白名单.版本不低于(r["固件版本"], 史[r["固件指纹"]]), (
            f"并发漏拦：{r['报文编号']} 固件 {r['固件版本']} 低于指纹 "
            f"{r['固件指纹']} 的最低版本 {史[r['固件指纹']]}"
        )
    assert len(入栏) + len(归档) == 15, "低版本未归档也未入栏，去向不可区分"
    for r in 归档:
        assert not 固件白名单.版本不低于(
            r["固件版本"], 史[r["固件指纹"]]
        ), "归档行并非低版本"
