#!/usr/bin/env python3
"""Knoa RAG 运转流程 + 回答正确性 评测脚本（零三方依赖，仅用标准库）。

用法:
    cd backend
    .venv/Scripts/python.exe loadtests/rag_eval.py

输出:
    loadtests/rag_eval_report.json   每题原始记录 + 自动判定
    loadtests/rag_eval_report.md    人读版报告

判定维度（自动）:
    - 流程正确性: 是否走 route->retrieve->generate 线性; 有无死循环;
      trivial 类是否正确跳过检索; 空库/超范围是否诚实"没找到"。
    - 溯源正确性(部分): 答案里的 [n] 角标是否落在召回来源编号范围内;
      retrieve 类题目来源数是否 >0。
    语义正确性(答案对不对) 留给人工在报告里判读。
"""
import json
import ssl
import time
import urllib.request
import urllib.error
import re

BASE = "https://localhost:8000"
LOGIN = "/api/auth/login"
ASK = "/api/ask"
USER = "admin"
PASS = "admin123"

HONEST_MARKERS = ["没找到", "无法找到", "不在知识库", "库里没有", "未找到", "没有找到相关内容", "知识库中没有", "不在当前"]

# ---- 测试用例 ----
# expect: retrieve | skip | empty | web | honest_or_web
CASES = [
    # 合规政策 compliance
    dict(id="C01", kb="compliance", cat="事实查询", expect="retrieve",
         q="亚马逊账户健康评级（AHR）达到什么阈值会收到警告？"),
    dict(id="C02", kb="compliance", cat="操作类", expect="retrieve",
         q="账号被封后，一封有效的 POA 行动计划应包含哪几个部分？"),
    dict(id="C03", kb="compliance", cat="故障排查", expect="retrieve",
         q="收到商标侵权投诉应该怎么申诉移除？"),
    dict(id="C04", kb="compliance", cat="对比分析", expect="retrieve",
         q="账户健康评级和传统 ODR 指标，哪个对封号影响更大？"),
    dict(id="C05", kb="compliance", cat="策略开放", expect="retrieve",
         q="新账号应该怎么预防店铺被封？"),

    # 广告运营 ads
    dict(id="A01", kb="ads", cat="事实查询", expect="retrieve",
         q="亚马逊 SP 广告的默认竞价策略有哪几种？"),
    dict(id="A02", kb="ads", cat="操作类", expect="retrieve",
         q="新品广告冷启动期应该怎么设置预算和竞价？"),
    dict(id="A03", kb="ads", cat="故障排查", expect="retrieve",
         q="广告点击率正常但 ACOS 过高应该怎么优化？"),
    dict(id="A04", kb="ads", cat="对比分析", expect="retrieve",
         q="SB 和 SD 广告分别适合在什么场景投放？"),
    dict(id="A05", kb="ads", cat="策略开放", expect="retrieve",
         q="月预算 2000 美元，应该怎么分配在品牌词和品类词上？"),

    # 物流仓储 logistics
    dict(id="L01", kb="logistics", cat="事实查询", expect="retrieve",
         q="FBA 头程海运和空运大概的时效和成本差异是多少？"),
    dict(id="L02", kb="logistics", cat="操作类", expect="retrieve",
         q="怎么计算一个产品发 FBA 需要多少库存覆盖？"),
    dict(id="L03", kb="logistics", cat="故障排查", expect="retrieve",
         q="FBA 旺季仓储附加费一般在什么时间开始收取？"),
    dict(id="L04", kb="logistics", cat="对比分析", expect="retrieve",
         q="FBA 和第三方海外仓各自适合什么体量的卖家？"),
    dict(id="L05", kb="logistics", cat="策略开放", expect="retrieve",
         q="小批量新手第一批发货应该怎么选头程方式？"),

    # 选品策略 selection
    dict(id="S01", kb="selection", cat="事实查询", expect="retrieve",
         q="选品时用来判断蓝海的核心指标有哪些？"),
    dict(id="S02", kb="selection", cat="操作类", expect="retrieve",
         q="怎么用卖家精灵之类的工具做竞品销量估算？"),
    dict(id="S03", kb="selection", cat="故障排查", expect="retrieve",
         q="一个品类评论数很高但评分在下降，说明什么问题？"),
    dict(id="S04", kb="selection", cat="对比分析", expect="retrieve",
         q="红海和蓝海选品，运营资源投入有什么不同？"),
    dict(id="S05", kb="selection", cat="策略开放", expect="retrieve",
         q="资金只有 5 万、想小批量试错，选品上应该怎么设置门槛？"),

    # 客户服务 service
    dict(id="V01", kb="service", cat="事实查询", expect="retrieve",
         q="亚马逊的退货政策里，哪些情况买家不能无故退货？"),
    dict(id="V02", kb="service", cat="操作类", expect="retrieve",
         q="遇到 1 到 2 星的差评，客服应该怎么跟进挽回？"),
    dict(id="V03", kb="service", cat="故障排查", expect="retrieve",
         q="买家说没收到货但要求退款，应该怎么处理？"),
    dict(id="V04", kb="service", cat="对比分析", expect="retrieve",
         q="站内信和 A-to-z 索赔，哪种对账户风险更大？"),
    dict(id="V05", kb="service", cat="策略开放", expect="retrieve",
         q="怎么设计一套标准化的售前加售后客服话术？"),

    # 边缘 / 异常
    dict(id="E01", kb=None, cat="跨域综合", expect="retrieve",
         q="选品阶段怎么结合广告 ACOS 数据判断一个品类值不值得长期做？"),
    dict(id="E02", kb=None, cat="超范围-代码", expect="honest_or_web",
         q="帮我写一段 Python 爬虫代码"),
    dict(id="E03", kb=None, cat="超范围-实时", expect="web",
         q="今天美股大盘行情怎么样？"),
    dict(id="E04", kb=None, cat="闲聊", expect="skip",
         q="你好"),
    dict(id="E05", kb=None, cat="数学计算", expect="skip",
         q="帮我算一下 125 乘以 8 等于多少"),
    dict(id="E06", kb=None, cat="模糊无上下文", expect="honest_or_web",
         q="这个要怎么办？"),
    dict(id="E07", kb="demo_empty", cat="空库检索", expect="empty",
         q="FBA 头程有哪几种方式？"),

    # 多轮（E08 是 E08a 的追问，共享 session）
    dict(id="E08a", kb="logistics", cat="多轮-首轮", expect="retrieve",
         q="FBA 头程有哪几种方式？"),
    dict(id="E08b", kb="logistics", cat="多轮-追问", expect="retrieve",
         q="那小批量新手最适合哪种？", use_session_of="E08a"),
]


def log(*a):
    print("[rag_eval]", *a, flush=True)


class Client:
    def __init__(self):
        self.ctx = ssl.create_default_context()
        self.ctx.check_hostname = False
        self.ctx.verify_mode = ssl.CERT_NONE
        self.token = None

    def _login(self):
        body = json.dumps({"username": USER, "password": PASS}).encode()
        req = urllib.request.Request(
            BASE + LOGIN, data=body,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, context=self.ctx, timeout=30) as r:
            self.token = json.loads(r.read().decode()).get("accessToken")
        log("login ok, token len =", len(self.token or ""))

    def ask(self, question, kb=None, session_id=None):
        if not self.token:
            self._login()
        body = json.dumps({
            "question": question,
            "knowledgeBase": kb,
            "sessionId": session_id,
            "files": [],
        }).encode()
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
            "Accept": "text/event-stream",
        }
        req = urllib.request.Request(
            BASE + ASK, data=body, headers=headers, method="POST")
        try:
            resp = urllib.request.urlopen(req, context=self.ctx, timeout=300)
        except urllib.error.HTTPError as e:
            if e.code == 401:
                self._login()
                req.headers["Authorization"] = f"Bearer {self.token}"
                resp = urllib.request.urlopen(req, context=self.ctx, timeout=300)
            else:
                raise

        record = {
            "thinking": [],   # list of {step, action, detail}
            "sources": [],     # list of {id, title, kb, source_type}
            "answer": "",
            "citations": [],
            "error": None,
        }
        event = None
        data_lines = []
        for raw in resp:
            line = raw.decode("utf-8", "replace")
            if line in ("\n", "\r\n"):
                if event and data_lines:
                    self._dispatch(event, "\n".join(data_lines), record)
                event, data_lines = None, []
                if record["error"]:
                    break
                continue
            if line.startswith("event:"):
                event = line[6:].strip()
            elif line.startswith("data:"):
                data_lines.append(line[5:].lstrip())
        # 收尾
        if event and data_lines:
            self._dispatch(event, "\n".join(data_lines), record)
        return record

    @staticmethod
    def _dispatch(event, payload, record):
        try:
            d = json.loads(payload)
        except Exception:
            return
        if event == "thinking":
            record["thinking"].append({
                "step": d.get("step"),
                "action": d.get("action"),
                "detail": d.get("detail", ""),
            })
        elif event == "sources":
            for s in d:
                record["sources"].append({
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "kb": s.get("kb"),
                    "source_type": s.get("source_type", "kb"),
                })
        elif event == "delta":
            record["answer"] += d.get("content", "")
        elif event == "done":
            record["citations"] = d.get("citations", [])
            record["sessionId"] = d.get("sessionId")
        elif event == "error":
            record["error"] = d.get("message")


def analyze(case, rec):
    actions = [t["action"] for t in rec["thinking"]]
    n_src = len(rec["sources"])
    ans = rec["answer"]
    cited = sorted(set(int(x) for x in re.findall(r"\[(\d+)\]", ans)))
    max_src_id = max((s["id"] for s in rec["sources"] if isinstance(s["id"], int)), default=0)
    citations_valid = all(1 <= i <= max_src_id for i in cited) if cited else (n_src == 0)
    has_web = any(s["source_type"] == "web" for s in rec["sources"])
    honest = any(m in ans for m in HONEST_MARKERS)
    loop = len(rec["thinking"]) > 4  # 正常线性最多 3 步(route/retrieve/generate)
    flow_ok = True
    notes = []
    exp = case["expect"]

    if exp == "retrieve":
        if n_src == 0:
            flow_ok = False
            notes.append("期望检索但来源数为 0")
        if not cited:
            flow_ok = False
            notes.append("答案无 [n] 引用角标")
        if loop:
            flow_ok = False
            notes.append("思考步数>4，疑似死循环")
        if "retrieve" not in actions and "supplement_search" not in actions and "web_search" not in actions:
            flow_ok = False
            notes.append("思考链完全未出现检索动作")
    elif exp == "skip":
        if n_src > 0:
            flow_ok = False
            notes.append("trivial 类却发生了检索")
        if loop:
            flow_ok = False
            notes.append("思考步数异常")
    elif exp == "empty":
        if n_src > 0 and not honest:
            flow_ok = False
            notes.append("空库却召回来源且未诚实说明")
        if n_src == 0 and not honest and not cited:
            notes.append("空库且未明确说没找到（可能编造，需人工看）")
    elif exp == "web":
        if not has_web and not honest and n_src == 0:
            notes.append("未走联网也未诚实说明，需人工看")
    elif exp == "honest_or_web":
        if n_src > 0 and cited:
            pass  # 有来源且引用，算正常
        elif n_src == 0 and not honest:
            notes.append("无来源且未诚实说明，需人工看是否编造")

    if rec["error"]:
        flow_ok = False
        notes.append(f"ERROR: {rec['error']}")

    return {
        "actions": actions,
        "n_sources": n_src,
        "cited_indices": cited,
        "citations_valid": citations_valid,
        "has_web": has_web,
        "honest": honest,
        "loop_suspect": loop,
        "flow_ok": flow_ok,
        "notes": notes,
    }


def main():
    cli = Client()
    results = []
    by_id = {}
    t0 = time.time()
    for i, case in enumerate(CASES, 1):
        log(f"=== [{i}/{len(CASES)}] {case['id']} ({case['cat']}) ===")
        log("Q:", case["q"][:60])
        session_of = case.get("use_session_of")
        sid = by_id[session_of]["sessionId"] if session_of else None
        rec = cli.ask(case["q"], kb=case["kb"], session_id=sid)
        ana = analyze(case, rec)
        entry = {
            "id": case["id"],
            "cat": case["cat"],
            "kb": case["kb"],
            "expect": case["expect"],
            "question": case["q"],
            "sessionId": rec.get("sessionId"),
            "thinking": rec["thinking"],
            "n_sources": ana["n_sources"],
            "sources": [{"id": s["id"], "title": s["title"], "kb": s["kb"], "type": s["source_type"]} for s in rec["sources"]],
            "cited_indices": ana["cited_indices"],
            "citations_valid": ana["citations_valid"],
            "has_web": ana["has_web"],
            "honest": ana["honest"],
            "loop_suspect": ana["loop_suspect"],
            "flow_ok": ana["flow_ok"],
            "notes": ana["notes"],
            "answer": rec["answer"],
            "error": rec["error"],
        }
        by_id[case["id"]] = entry
        results.append(entry)
        # 实时落盘（防中途崩溃丢数据）
        _write(results, time.time() - t0)
        log("  来源数=%d 引用=%s 流程OK=%s 备注=%s" % (
            ana["n_sources"], ana["cited_indices"], ana["flow_ok"], ana["notes"] or "-"))
    log("ALL DONE, 用时 %.1fs" % (time.time() - t0))


def _write(results, elapsed):
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(out_dir, "rag_eval_report.json"), "w", encoding="utf-8") as f:
        json.dump({"elapsed_sec": elapsed, "cases": results}, f, ensure_ascii=False, indent=2)
    _write_md(results, elapsed, os.path.join(out_dir, "rag_eval_report.md"))


def _write_md(results, elapsed, path):
    lines = ["# Knoa RAG 评测报告", "",
             f"> 生成时间耗时: {elapsed:.1f}s  用例数: {len(results)}", "",
             "## 摘要", ""]
    ok = sum(1 for r in results if r["flow_ok"])
    loops = sum(1 for r in results if r["loop_suspect"])
    retr = sum(1 for r in results if r["n_sources"] > 0)
    cit = sum(1 for r in results if r["cited_indices"])
    lines.append(f"- 流程自动判定通过: **{ok}/{len(results)}**")
    lines.append(f"- 疑似死循环: **{loops}**")
    lines.append(f"- 发生检索(来源>0): **{retr}/{len(results)}**")
    lines.append(f"- 答案带 [n] 引用: **{cit}/{len(results)}**")
    lines.append("")
    lines.append("## 逐题记录")
    lines.append("")
    for r in results:
        lines.append(f"### {r['id']} · {r['cat']}  (期望: {r['expect']})")
        lines.append(f"- 问题: {r['question']}")
        lines.append(f"- 知识库: `{r['kb']}`")
        actions = " → ".join(str(a) for a in [t['action'] for t in r['thinking']]) or "(无思考事件)"
        lines.append(f"- 思考链: {actions}")
        lines.append(f"- 来源数: {r['n_sources']}  引用角标: {r['cited_indices']}  引用合法: {r['citations_valid']}  "
                     f"联网: {r['has_web']}  诚实兜底: {r['honest']}")
        if r["sources"]:
            for s in r["sources"][:8]:
                lines.append(f"  - [{s['id']}] {s['title']}  (`{s['kb']}`/{s['type']})")
        lines.append(f"- **流程OK**: {r['flow_ok']}  {' 备注: ' + str(r['notes']) if r['notes'] else ''}")
        lines.append(f"- 答案摘要: {r['answer'][:300]}{'…' if len(r['answer'])>300 else ''}")
        lines.append("- [ ] **人工判读**: 答案是否与知识库内容一致？( ) 一致 ( ) 部分一致 ( ) 不一致/编造")
        lines.append("")

    # 待人工重点看的项
    risk = [r for r in results if (not r["flow_ok"]) or (r["n_sources"] == 0 and r["expect"] == "retrieve")]
    if risk:
        lines.append("## ⚠️ 需重点复核")
        for r in risk:
            lines.append(f"- {r['id']} ({r['cat']}): {r['notes'] or 'retrieve 但无来源'}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
