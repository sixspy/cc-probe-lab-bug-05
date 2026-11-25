from pathlib import Path
from quart import Quart, jsonify, request, send_from_directory, redirect
from app import seed
from app.services import 目录, 装载, 结栏, 贯验, 夹具, 统计, 说明
from app.services import fwgate as fwgate_svc
from app.services import fwgate_cutover as fwgate_cut_svc
from app.services import fwgate_dualwrite as fwgate_dual_svc
from app.services import fwgate_audit as fwgate_audit_svc
from app.services import 固件白名单 as 固件白名单_svc

_STATIC = Path(__file__).resolve().parent / "static"
app = Quart(__name__)


@app.before_serving
async def _boot():
    seed.初始化库()


@app.get("/login")
async def login_page():
    return await send_from_directory(_STATIC, "login.html")


@app.get("/")
async def index():
    return await send_from_directory(_STATIC, "index.html")


@app.get("/api/概览")
async def api_概览():
    return jsonify(目录.概览())


@app.get("/api/仓情")
async def api_仓情():
    return jsonify(说明.仓情())


@app.get("/api/栏规")
async def api_栏规_get():
    return jsonify(目录.栏规())


@app.post("/api/栏规")
async def api_栏规_post():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(目录.改栏规(body))


@app.get("/api/站点源")
async def api_站点():
    return jsonify(目录.站点列表())


@app.get("/api/观测报文")
async def api_报文():
    return jsonify(目录.报文列表())


@app.get("/api/入栏缓冲")
async def api_缓冲():
    return jsonify(目录.缓冲列表())


@app.get("/api/站点汇总账")
async def api_汇总():
    return jsonify(目录.汇总列表())


@app.get("/api/坏点匣")
async def api_坏点():
    return jsonify(目录.坏点列表())


@app.get("/api/栏贯验")
async def api_贯验列表():
    return jsonify(目录.贯验列表())


@app.get("/api/夹具")
async def api_夹具():
    return jsonify(夹具.列表())


@app.post("/api/观测报文/装载")
async def api_装载():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(装载.装一批(body))


@app.post("/api/观测报文/夹具/<name>")
async def api_夹具装载(name: str):
    try:
        return jsonify(装载.装一批(夹具.读取(name)))
    except FileNotFoundError:
        return jsonify({"错误": name}), 404


@app.post("/api/结栏/跑")
async def api_结栏():
    return jsonify(结栏.结当前栏())


@app.get("/api/结栏/预览")
async def api_结栏预览():
    return jsonify(结栏.预览结栏())


@app.get("/api/栏贯验/快照")
async def api_贯验快照():
    return jsonify(贯验.只读快照())


@app.get("/api/夹具/预检")
async def api_夹具预检():
    return jsonify(夹具.全部预检())


@app.post("/api/栏贯验/跑")
async def api_贯验():
    return jsonify(贯验.跑一次())


@app.get("/api/统计/报文命运")
async def api_统计报文():
    return jsonify(统计.报文命运())


@app.get("/api/统计/缓冲命运")
async def api_统计缓冲():
    return jsonify(统计.缓冲命运())




@app.get("/api/装载批次")
async def api_装载批次():
    return jsonify(目录.装载批次列表())


@app.get("/api/结栏批次")
async def api_结栏批次():
    return jsonify(目录.结栏批次列表())


@app.get("/api/统计/按站点")
async def api_按站点():
    return jsonify(统计.按站点报文())


@app.get("/api/统计/按指标")
async def api_按指标():
    return jsonify(统计.按指标汇总())


@app.get("/api/统计/装载摘要")
async def api_装载摘要():
    return jsonify(统计.装载批次摘要())


@app.get("/api/统计/结栏摘要")
async def api_结栏摘要():
    return jsonify(统计.结栏批次摘要())

@app.get("/api/空桩")
async def api_空桩():
    root = Path(__file__).resolve().parent / "modules"
    out = []
    if root.is_dir():
        for p in sorted(root.iterdir()):
            if p.is_dir() and p.name != "__pycache__" and (p / "__init__.py").is_file():
                out.append(p.name)
    return jsonify({"空桩": out, "条数": len(out)})


@app.get("/<path:name>")
async def static_page(name: str):
    p = _STATIC / name
    if not p.is_file():
        return redirect("/")
    return await send_from_directory(_STATIC, name)


@app.get("/api/fwgate/看板")
async def api_fwgate_board():
    return jsonify(fwgate_svc.dashboard())


@app.post("/api/fwgate/动作")
async def api_fwgate_action():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(fwgate_svc.commit_action(body))


@app.post("/api/fwgate/半修展示")
async def api_fwgate_half():
    return jsonify(fwgate_svc.half_fix_display())


@app.get("/api/fwgate/切流")
async def api_fwgate_cut():
    return jsonify(fwgate_cut_svc.board())


@app.post("/api/fwgate/切流")
async def api_fwgate_cut_post():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(fwgate_cut_svc.append_cutover(int(body.get("ref_id") or 1), str(body.get("note") or "")))


@app.get("/api/fwgate/双写")
async def api_fwgate_dual():
    return jsonify(fwgate_dual_svc.dual_board())


@app.post("/api/fwgate/双写")
async def api_fwgate_dual_post():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(fwgate_dual_svc.apply_dualwrite(str(body.get("note") or "")))


@app.get("/api/fwgate/审计")
async def api_fwgate_audit():
    return jsonify(fwgate_audit_svc.audit_summary())


@app.get("/api/固件门禁")
async def api_固件门禁():
    return jsonify(固件白名单_svc.门禁看板())


@app.get("/api/固件门禁/对账")
async def api_固件对账():
    return jsonify(固件白名单_svc.对账())


@app.get("/api/固件门禁/站点源对账")
async def api_固件站点源对账():
    return jsonify(固件白名单_svc.站点源对账())


@app.post("/api/固件门禁/白名单")
async def api_固件白名单设():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(固件白名单_svc.设最低版本(
        str(body.get("最低版本") or ""), str(body.get("备注") or "")
    ))


@app.post("/api/固件门禁/探头")
async def api_固件探头登记():
    body = await request.get_json(force=True, silent=True) or {}
    return jsonify(固件白名单_svc.登记探头(
        str(body.get("站点键") or ""), str(body.get("固件版本") or "")
    ))


@app.get("/api/固件门禁/归档")
async def api_固件归档():
    return jsonify(固件白名单_svc.归档列表())
