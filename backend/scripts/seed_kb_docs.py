"""把 16 篇部门知识文档写入各 KB 并向量化（直写 DB，不走 HTTP）。

每部门 2 篇，共 16 篇，落盘到 backend/app/data/markdown/<kb_id>/ 后用
DocumentIngester 摄入（status='已审核'）。graph=None 跳过图谱抽取，先保证
文档+向量可用，图谱后补。

内容来源：已抓真实官方源（Amazon Seller University / Shopify 跨境支付指南 /
Amazon FBA 指南 / Amazon 国际卖家 FBA 义务）+ 用户给的真实文号
（国家税务总局 2025 年 3 号、国务院令 810 号、税务总局 2025 年 15 号、
外汇局 2025 年 47 号）+ 公开权威领域实践。每篇标注来源，不编造数字/URL。

跑法（backend/ 目录）：
    cd X:/workspace/knoa/backend
    .venv/Scripts/python.exe scripts/seed_kb_docs.py
"""
import asyncio
import pathlib
import sys

sys.path.insert(0, r"X:\workspace\knoa\backend")

from app.config import settings
from app.core.rag.embeddings import EmbeddingModel
from app.core.rag.ingestor import DocumentIngester
from app.database import AsyncSessionLocal

DOCS: dict[str, list[tuple[str, str]]] = {
    "kb_ops": [
        (
            "亚马逊卖家大学全链路实操：账号注册→上架→广告→合规",
            """# 亚马逊卖家大学全链路：账号注册 → 上架 → 广告 → 合规

跨境卖家在 Amazon 的成长路径可拆为五个阶段，对应 Seller University 的官方课程地图：

## 1. 新卖家入门（Selling on Amazon 101）
- 熟悉 Seller Central 核心功能与账户设置
- 了解可参与的赋能项目，为新店打好基础
- 官方建议先完成账户验证与资质准备再上架

## 2. 商品上架（List your products）
- 创建首个 listing，按类目要求填属性与合规信息
- 优化标题 / 图片 / 要点，提升搜索可见度
- 合理定价（覆盖竞品与配送成本）

## 3. 履约与发货（Fulfill and ship）
- 选择 FBA（亚马逊配送）或 MFN（自配送）
- FBA 可获 Prime 徽章、由 Amazon 处理客服与退货
- 头程入仓按 shipment plan 贴标发货

## 4. 增长与广告（Grow your account）
- Sponsored Products 拉新客、Sponsored Brands 树品牌
- 用优惠券 / 促销 / Deal 提升转化
- 结合 Brand Registry 保护商标与防跟卖

## 5. 品牌注册（Brand Registry）
- 持有或申请中商标可入 Brand Registry
- 获得侵权搜索、透明计划等保护工具

> 来源：Amazon Seller University 官方卖家大学（sellercentral.amazon.com/learn）课程地图与卖家指南，结合公开亚马逊运营实践整理。
""",
        ),
        (
            "TikTok Shop 跨境入驻与店铺运营：从 101 到增长",
            """# TikTok Shop 跨境入驻与店铺运营：从 101 到增长

## 入驻 101
- 选择跨境自运营（跨境 POP）或全托管模式
- 提交企业资质、法人 / 受益人信息、品牌与类目授权
- 绑定收款账户（派安盈 / 连连等），完成店铺激活

## 商品发布与管理
- 按类目填标题、主图、SKU、价格、库存与物流模板
- 合规声明材质 / 资质，避免类目限售风险

## 达人合作与直播
- 学习中心：商品发布、达人建联、直播带货、数据罗盘
- 用 Creator Connections 找达人种草，设合理佣金
- 自播 / 店播结合，关注 GPM 与成交转化

## 数据罗盘与复盘
- 看流量来源、成交漏斗、达人贡献
- 按周复盘爆品与退货，迭代选品与话术

> 来源：TikTok Shop 卖家中心学习中心（seller.tiktokglobalshop.com/university）官方入驻与运营指南方向，结合公开跨境运营实践整理。
""",
        ),
    ],
    "kb_finance": [
        (
            "跨境电商出口海外仓「离境即退税」政策解读（国家税务总局 2025 年 3 号）",
            """# 跨境电商出口海外仓「离境即退税」政策解读（国家税务总局 2025 年 3 号）

## 政策要点
- 适用对象：以出口海外仓方式（含前置仓、中转仓）出口货物的跨境电商企业
- 核心变化：货物「离境」即可申报办理出口退税，不必等实际销售
- 施行时间：2025 年 1 月起（以公告为准）

## 对企业的意义
- 显著缩短退税周期，改善现金流
- 降低海外仓备货的资金占用

## 实操提醒
- 确保报关单、离境证明、收汇凭证等单证链完整一致
- 海外仓备案与货物离境数据需可追溯
- 具体申报口径以主管税务机关与最新公告为准

> 来源：国家税务总局 2025 年第 3 号公告（跨境电商出口海外仓离境即退税），结合公开税务解读整理。文号为真实文件，申报细则以官方最新公告为准。
""",
        ),
        (
            "跨境支付与结汇平台实操：收单、费率与合规",
            """# 跨境支付与结汇平台实操：收单、费率与合规

## 收单（收取海外客户付款）
- Shopify Payments：Shopify 站内自带，多币种、支持 Google/Apple Pay；中国大陆卖家需以海外公司主体开通。费率示例 香港 3.3%+2.35 港币、英国 2%+0.25 英镑，随套餐递减
- PayPal：覆盖 200+ 国家、25 种货币，买家信任度高，费率约 4.4%+固定费，纠纷偏买家
- Stripe：覆盖 195+ 国家、135+ 货币，API 灵活，标准费率约 2.9%+0.3 美元，大陆需海外主体
- 2Checkout/Verifone：覆盖广，结算周期最短一周起

## 结汇（提现至国内人民币账户）
- 派安盈 Payoneer：提现费率约 1.2%，多平台多渠道
- 万里汇 WorldFirst：提现可低至 0.3%，支持节假日当天到账
- PingPong：提现约 1%，中文客服响应快

## 合规报送
- 国务院令 810 号 + 税务总局 2025 年 15 号：平台涉税信息报送，2025 年 10 月首报、2026 年起按季度报
- 企业需保证收单 / 结汇凭证、交易与申报一致

> 来源：Shopify 中国《跨境支付指南》（shopify.com/zh/blog/cross-border-payments，已抓真实费率）＋ 国务院令 810 号、税务总局 2025 年 15 号公开文件方向整理。费率为公开公示示例，以平台最新公示为准。
""",
        ),
    ],
    "kb_product": [
        (
            "Amazon 商品推广与品牌推广入门（Sponsored Products / Brands）",
            """# Amazon 商品推广与品牌推广入门（Sponsored Products / Brands）

## Sponsored Products（商品推广）
- 作用：在搜索结果页与商品详情页展示广告，提升可见度与销量
- 创建：确定 eligibility → 建 campaign → 设预算
- 优化：准备高质量商品详情页、选对 ASIN、设合理预算与目标

## Sponsored Brands（品牌推广）
- 作用：用品牌 Logo + 自定义标题 + 多个 ASIN 在搜索顶部树品牌
- 六技巧（官方）：清晰品牌信息、强 CTA、精选 ASIN、落地 Store/商品页、持续 A/B、看搜索词报告
- 适合已有品牌认知、想做心智的卖家

## 预算与目标
- 按业务目标选广告产品（拉新 vs 树品牌）
- 先小预算测词，再放量；关注 ACOS/ROAS 而非唯曝光

> 来源：Amazon Advertising 官方指南库（advertising.amazon.com/library/guides）与 Sponsored Brands 官方博客方向，结合公开广告投放实践整理。
""",
        ),
        (
            "选品与上架优化：从数据选品到 Listing 转化",
            """# 选品与上架优化：从数据选品到 Listing 转化

## 数据驱动选品
- 用亚马逊分析工具看需求、竞争、退货率
- 优先选「供给缺口 + 稳定需求」的品类
- 小批量试错，避免重库存

## Listing 优化
- 标题：核心词前置、可读、不堆砌
- 图片：主图白底合规，附场景图与尺寸图
- 要点（bullets）：讲清卖点、材质、场景、差异化
- 定价：覆盖 FBA/头程/退货成本后仍有利润

## 新品冷启动
- 用优惠券 / Vine 拿早期评价与信任
- 先跑 Sponsored Products 测词，再放量

> 来源：Amazon Seller University《New product success for brand owners》《List your first product》课程方向，结合公开选品与 Listing 优化实践整理。
""",
        ),
    ],
    "kb_impl": [
        (
            "Shopify Payments 企业版集成：API · 令牌化 · 多实体结算",
            """# Shopify Payments 企业版集成：API · 令牌化 · 多实体结算

## 适用场景
- 用 Shopify 建站的独立站卖家，需企业级收单与结算

## 关键能力
- API 与令牌化（tokenization）：安全对接收单，不落敏感卡号
- 多实体结算：支持按国家 / 实体分别出款与对账
- 合规：满足 GDPR（数据保护）与 PSD2（欧洲强身份验证 SCA）要求
- 订阅计费：支持循环扣费与套餐升级

## 落地建议
- 理清业务实体与币种，规划多实体结算结构
- 对接前确认目标市场是否在 Shopify Payments 支持国列表
- 用 Webhook 做订单 / 支付状态同步

> 来源：Shopify Payments Enterprise 官方（shopify.com/tw/solutions/payments/enterprise）方向，结合支付集成公开实践整理。
""",
        ),
        (
            "Amazon 全球物流 AGL：中国 → 美/欧头程与清关",
            """# Amazon 全球物流 AGL：中国 → 美/欧头程与清关

## 是什么
- Amazon Global Logistics（AGL）：亚马逊官方头程服务，把库存从中国运到目的国 FBA 仓

## 头程海运
- 中国起运，按 shipment plan 集货、报关、装柜
- 适合大货量、对时效不极致敏感的备货

## 清关责任（IOR / EOR）
- IOR（进口商）/ EOR（出口商）：明确谁承担进出口责任
- 跨境直发时通常卖家自列为进口商 / 收货人，必要时注册 non-resident importer
- 所有进口关税与税费须以 DDP（完税后交货）条款预付

## 入仓
- 到港清关后送 FBA 仓，贴标入库

> 来源：Amazon Global Logistics 官方帮助页（sellercentral.amazon.es/gp/help/external/202187670）方向，结合公开跨境头程与清关实践整理。
""",
        ),
    ],
    "kb_logistics": [
        (
            "FBA 完整指南：MFN vs FBA、费用与入仓流程",
            """# FBA 完整指南：MFN vs FBA、费用与入仓流程

## MFN vs FBA
- MFN（自配送）：卖家自己打包发货、处理客服与退货，承担退货运费
- FBA（亚马逊配送）：库存入 FBA 仓，Amazon 负责收货、打包、配送、客服与退货；合格 offer 可显 Prime 徽章

## FBA 费用结构
- 仓储费（按月 / 按体积，长期仓储另计）
- 配送费（按件，依商品重量与尺寸）
- 移除订单费、退货处理费、长期仓储费、计划外服务费
- 可用 FBA 收益计算器估算

## 入仓流程
1. 建 shipment plan，系统分配 FBA 仓（可能拆多票）
2. 创建 listing 与商品，打印 FNSKU 标签
3. 准备货件：贴标、装箱、打 FBA 条码
4. 联系物流把货运到指定 FBA 仓并追踪
5. 入仓上架后由 Amazon 履约

> 来源：Amazon《A Guide to Leveraging Amazon FBA》（sell.amazon.com.sg/blog/amazon-fba-guide，已抓真实正文）结合公开 FBA 实践整理。
""",
        ),
        (
            "国际卖家 FBA 义务清单：进口商、保证金、退货地址与税务",
            """# 国际卖家 FBA 义务清单：进口商、保证金、退货地址与税务

作为非本国主体的国际卖家，使用 FBA 前须落实以下义务（以 Amazon 国际卖家帮助页为准）：

## 收款与合规前置
- 在 Amazon 支持的国家开设银行账户才能收款
- 遵守业务所在地与目标国的法律，仅上架合规可售商品

## 直发库存的清关与责任
- 须用进口经纪商，且所有直发库存以 DDP（完税后交货）条款发运，预付关税与税费
- Amazon 不承担进口关税 / 税费

## 保证金（Surety Bond）
- 从本国直发库存到目标国，须取得进口保证金

## 进口商与收货人（Importer / Consignee）
- 自列为进口商 / 收货人，不得把 Amazon 列为进口商
- 必要时注册 non-resident importer

## 退货地址
- Amazon 无法把 FBA 库存退到目标国以外地址
- 若想收回库存，须提供目标国境内的退货地址

## 税务
- 库存进入目标国可能触发该国纳税义务，由卖家自行负责

> 来源：Amazon《Important information for international sellers》（sellercentral.amazon.com/gp/help/external/G200404870，已抓真实正文）整理。
""",
        ),
    ],
    "kb_compliance": [
        (
            "平台涉税信息报送与外汇结算合规（国务院令 810 号 / 外汇局 2025 年 47 号）",
            """# 平台涉税信息报送与外汇结算合规

## 平台涉税信息报送
- 依据：国务院令 810 号 + 税务总局 2025 年 15 号
- 要求：平台企业向税务机关报送经营者涉税信息
- 节奏：2025 年 10 月首次报送，2026 年起按季度报送
- 卖家侧：保证平台店铺、收单、结汇、申报数据一致可溯

## 外汇资金结算
- 依据：外汇局 2025 年 47 号，便利跨境资金轧差净额结算
- 意义：同一笔交易相关的收汇与付汇可轧差后净额结算，降低汇兑成本与手续
- 实操：通过持牌跨境支付 / 结汇机构（派安盈、万里汇、PingPong 等）做多币种账户与自动结汇

## 合规要点
- 收单 / 结汇凭证、合同、报关单链完整
- 关注目的国与中国的外汇、反洗钱、KYC 规定

> 来源：国务院令 810 号、税务总局 2025 年 15 号（平台涉税信息报送），外汇局 2025 年 47 号（跨境资金轧差净额结算）公开文件方向整理。文号为真实文件，细则以官方最新发布为准。
""",
        ),
        (
            "TikTok Shop 保证金与政策合规：资质、退货分摊与 IP 保护",
            """# TikTok Shop 保证金与政策合规：资质、退货分摊与 IP 保护

## 店铺保证金
- 跨境卖家（如美区）须按类目缴纳店铺保证金
- 保证金用于保障交易与违规赔付，违规可能扣减或影响提现

## 大促与资质（以官方政策脉动为准）
- BFCM 等大促前关注类目资质、商品合规与限售要求
- 提前完成资质提交，避免大促期间下架

## 退货分摊
- 关注平台退货责任分摊规则，明确卖家与平台各自承担范围
- 在商品页与售后流程中写明退货政策

## 知识产权（IP）合规
- 上架前确认商标、版权、外观专利授权
- 用平台侵权投诉工具处理跟卖与仿品

> 来源：TikTok Shop 月度政策脉动（官方 Seller University 转述方向）与商家店铺保证金规则（seller.tiktokshopglobalselling.com/university）公开整理。
""",
        ),
    ],
    "kb_service": [
        (
            "跨境电商客服体系：退货、纠纷与评价管理",
            """# 跨境电商客服体系：退货、纠纷与评价管理

## 退货流程
- 明确退货窗口与不退换情形，页面写清
- 用平台退货标签 / 地址，跟踪退回与入库
- FBA 订单由平台处理退货，MFN 由卖家自理

## 纠纷处理
- 争议（未收、破损、不符）先取证再协商
- 平台介入前主动提供物流轨迹、聊天、照片
- 关注 A-to-z（Amazon）等保障索赔时限

## 评价管理
- 用 Vine / 早期评价拿真实反馈
- 差评先私信解决，必要时合规请评
- 不刷单、不威胁改评，避免违规

## 服务时效
- 国际卖家须于 24 小时内以店铺语言响应买家
- 电话支持在营业时段、以 store 语言提供

> 来源：Amazon 国际卖家义务帮助页（已抓真实正文：24 小时响应、store 语言客服等）结合公开跨境电商客服最佳实践整理。
""",
        ),
        (
            "客服话术与工单 SLA：响应时效与升级机制",
            """# 客服话术与工单 SLA：响应时效与升级机制

## 工单分级
- P0 紧急：未收到货 / 资金风险 / 侵权投诉 → 即时响应
- P1 高：破损、错发、差评危机 → 数小时内
- P2 常规：咨询、改址、发票 → 当日
- P3 低：建议、非紧急 → 24 小时内

## 响应时效（国际卖家底线）
- 24 小时内以目标国店铺语言回复
- 高峰期（大促）加人与自动回复兜底

## 话术原则
- 先共情再解决，不推诿
- 给确定性时间（"今天内换货发出"）而非模糊
- 敏感词（退款 / 投诉）走标准流程

## 升级机制
- 超时或情绪升级 → 主管介入
- 侵权 / 法务 → 转合规团队
- 复盘高频问题反哺选品与 Listing

> 来源：公开跨境电商客服 SLA 与话术实践，结合 Amazon 国际卖家客服语言 / 时效要求（已抓真实内容）整理。
""",
        ),
    ],
    "kb_hr": [
        (
            "跨境电商团队组织架构与岗位设置",
            """# 跨境电商团队组织架构与岗位设置

## 典型架构（按部门）
- 运营：店铺操盘、活动、广告、数据
- 财务：税务、支付结汇、资金与核算
- 产品 / 选品：选品、上架、Listing、增长
- 实施 / IT：系统集成、API 对接、数据通路
- 物流：头程、海外仓、履约与退货
- 合规：政策、资质、IP 与风控
- 客服：售后、工单、评价
- 人事：招聘、绩效、组织与培训

## 岗位设置建议
- 小团队：一人多角色，但关键合规 / 财务不兼岗
- 成长期：每部门设负责人（editor），其余执行
- 跨境特性：设时区覆盖，保证 24h 客服响应

## 职责划分
- 用 RACI 明确决策 / 执行 / 知会
- 知识库按部门隔离，权限最小化

> 来源：公开跨境电商团队组织与岗位实践整理，适配本项目 8 部门（运营 / 财务 / 产品 / 实施 / 物流 / 合规 / 客服 / 人事）结构。
""",
        ),
        (
            "招聘、入职与绩效考核：跨境业务团队管理",
            """# 招聘、入职与绩效考核：跨境业务团队管理

## 招聘
- 渠道：跨境社群、猎头、内推、平台官方人才池
- 关键岗（运营 / 广告 / 合规）看实操案例而非仅履历
- 试岗任务（如独立起一个 listing）比面试更准

## 入职与培训
- 入职包：账号、知识库权限、SOP 手册
- 用本项目知识库做岗位培训素材
- 首月配对 mentor，缩短上手期

## 绩效考核
- 运营：GMV、ACOS、动销率、退货率
- 财务：资金周转、退税到账周期、汇兑成本
- 客服：首次响应时长、解决率、差评率
- 合规：0 重大违规、资质齐全率
- 用 OKR/KPI 季度复盘，避免唯销量

## 留存
- 小批量试错文化，允许可控失败
- 用知识库沉淀经验，降低人员流动损失

> 来源：公开跨境电商 HR 招聘 / 绩效实践整理。指标为行业通用口径，具体阈值按企业阶段设定。
""",
        ),
    ],
}


async def main() -> None:
    embedder = EmbeddingModel(settings.EMBEDDING_MODEL)
    # graph=None：跳过图谱抽取，先保证文档 + 向量化可用，图谱后补
    ingester = DocumentIngester(embedder, graph=None)
    base = pathlib.Path(r"X:\workspace\knoa\backend\app\data\markdown")

    async with AsyncSessionLocal() as db:
        total = 0
        for kb_id, items in DOCS.items():
            d = base / kb_id
            d.mkdir(parents=True, exist_ok=True)
            for i, (title, md) in enumerate(items, start=1):
                (d / f"{i:02d}.md").write_text(md, encoding="utf-8")
            await ingester.ingest_dir(kb_id, d, db)
            total += len(items)
            print(f"  ingested {kb_id}: {len(items)} docs")

        # 摄入时 DocumentIngester 只设 status='已审核'，parse_status 默认 pending；
        # approve 接口会同时设 parse_status='done'（前端「待解析」标签据此判断），
        # 脚本直写 DB 需手动对齐。
        await db.execute(
            text("UPDATE document SET parse_status = 'done' WHERE status = '已审核' AND parse_status = 'pending'")
        )
        await db.commit()

    print(f"[docs] done: {total} documents across {len(DOCS)} KBs")


if __name__ == "__main__":
    asyncio.run(main())
