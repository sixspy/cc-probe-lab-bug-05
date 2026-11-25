
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(url + " " + r.status);
  return r.json();
}
async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? "{}" : JSON.stringify(body),
  });
  const t = await r.text();
  let data;
  try { data = JSON.parse(t); } catch { data = { 原文: t }; }
  if (!r.ok) throw new Error((data && (data.错误 || data.detail)) || t || String(r.status));
  return data;
}
function 行(html) {
  const tr = document.createElement("tr");
  tr.innerHTML = html;
  return tr;
}
function 徽章(文, 类) {
  const tone = 类 || 命运色(文);
  return `<span class="徽章 ${tone || ""}">${安全文本(文)}</span>`;
}
function 空态(文) { return `<p class="说明">${安全文本(文)}</p>`; }
function 安全文本(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}
function 命运色(f) {
  if (["已入栏", "在栏", "已汇总", "对齐"].includes(f)) return "ok";
  if (["已坏点", "撕裂"].includes(f)) return "warn";
  return "";
}
function 渲染水位(el, o) {
  if (!el) return;
  el.innerHTML = "";
  for (const [标, 键] of [["观测报文","观测报文"],["在栏","在栏"],["站点汇总","站点汇总"],["坏点","坏点"]]) {
    const d = document.createElement("div");
    d.className = "水卡";
    d.innerHTML = `<div class="数">${o[键] ?? 0}</div><div class="标">${标}</div>`;
    el.appendChild(d);
  }
}
function 渲染门槛(el, 规) {
  if (!el) return;
  const r = 规 || {};
  el.innerHTML = `
    <div class="门槛卡"><div class="k">当前栏</div><div class="v">${安全文本(r["当前栏号"] || "—")}</div></div>
    <div class="门槛卡"><div class="k">PM25 上限</div><div class="v">${安全文本(r["PM25上限"] || "—")}</div></div>
    <div class="门槛卡"><div class="k">PM25 下限</div><div class="v">${安全文本(r["PM25下限"] || "—")}</div></div>
    <div class="门槛卡"><div class="k">标定偏移</div><div class="v">${安全文本(r["标定偏移上限"] || "—")}</div></div>
  `;
}
function 渲染批次表(el, rows, cols) {
  if (!el) return;
  if (!rows || !rows.length) {
    el.innerHTML = `<tr><td colspan="${cols.length}">${空态("尚无批次。")}</td></tr>`;
    return;
  }
  el.innerHTML = "";
  for (const r of rows) {
    const cells = cols.map((c) => `<td>${安全文本(r[c])}</td>`).join("");
    el.appendChild(行(cells));
  }
}
function 装载摘要文(r) {
  if (!r) return "";
  return `入流 ${r["入流"]||0} · 入栏 ${r["入栏"]||0} · 坏点 ${r["坏点"]||0} · 驳回 ${r["驳回"]||0}`;
}
function 结栏摘要文(r) {
  if (!r) return "";
  return `栏 ${r["栏号"]||"?"} · 汇总 ${r["汇总数"]||0} · 缓冲消耗 ${r["缓冲消耗"]||0}`;
}
function 贯验摘要文(r) {
  if (!r) return "";
  return `${r["是否对齐"]?"对齐":"撕裂"} · 在栏 ${r["在栏"]} · 汇总报文 ${r["汇总报文"]} · 坏点 ${r["坏点"]}`;
}
function 填命运字典(el, dict) {
  if (!el || !dict) return;
  el.innerHTML = Object.entries(dict).map(([k, v]) =>
    `<div class="只读框 上距8"><b class="铜字">${安全文本(k)}</b> · ${安全文本(v)}</div>`
  ).join("");
}

function 固件灯(值) {
  const 红 = String(值 || "").includes("红");
  return `<span class="徽章 ${红 ? "危" : "好"}">${安全文本(值 || "—")}</span>`;
}
function 渲染固件门禁(el, 账) {
  if (!el) return;
  if (!账) { el.innerHTML = 空态("固件门禁账未读到。"); return; }
  const 灯行 = (账.明细 || []).map((d) =>
    `<tr><td>${安全文本(d.站点键)}</td><td>${安全文本(d.登记固件 || "—")}</td><td>${固件灯(d.灯)}</td>` +
    `<td>${d.入栏笔数}</td><td>${d.低版入栏笔数}</td><td>${d.归档笔数}</td><td>${d.拦截笔数}</td></tr>`
  ).join("");
  el.innerHTML = `
    <div class="门槛条" style="margin-bottom:10px">
      <div class="门槛卡"><div class="k">形态</div><div class="v">${安全文本(账.形态 || "凭证表+只读归档")}</div></div>
      <div class="门槛卡"><div class="k">最低固件</div><div class="v">${安全文本(账.最低版本 || "—")}</div></div>
      <div class="门槛卡"><div class="k">白名单指纹</div><div class="v" style="font-size:13px">${安全文本(账.指纹 || "—")}</div></div>
      <div class="门槛卡"><div class="k">对账</div><div class="v">${固件灯(账.状态)}</div></div>
    </div>
    <div class="横排 下距12">
      <div class="水卡"><div class="数">${账.拦截笔数 ?? 0}</div><div class="标">低版本拦截</div></div>
      <div class="水卡"><div class="数">${账.归档笔数 ?? 0}</div><div class="标">只读归档</div></div>
      <div class="水卡"><div class="数">${账.现行入栏笔数 ?? 0}</div><div class="标">现行入栏</div></div>
      <div class="水卡"><div class="数">${账.现行入栏低版行 ?? 0}</div><div class="标">漏检入栏</div></div>
    </div>
    <p class="说明">读引用：现行入栏只收达标固件集；低版本报文只进只读归档，不参与结栏汇总。灯红且有入栏即对账不合法。</p>
    <div class="表绕"><table><thead><tr><th>站点</th><th>登记固件</th><th>灯</th><th>现行入栏</th><th>低版入栏</th><th>只读归档</th><th>拦截</th></tr></thead><tbody>${灯行 || `<tr><td colspan="7">${空态("尚无站点固件登记。")}</td></tr>`}</tbody></table></div>
  `;
}
function 固件拦截摘要(r) {
  if (!r) return "";
  return `入栏 ${r["入栏"]||0} · 坏点 ${r["坏点"]||0} · 固件拦截 ${r["固件拦截"]||0} · 归档 ${r["归档"]||0}`;
}
window.探栏 = {
  getJSON, postJSON, 行, 徽章, 空态, 安全文本, 命运色,
  渲染水位, 渲染门槛, 渲染批次表,
  装载摘要文, 结栏摘要文, 贯验摘要文, 填命运字典,
  固件灯, 渲染固件门禁, 固件拦截摘要,
};
