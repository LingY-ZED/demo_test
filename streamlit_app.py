"""
火眼智擎 - Streamlit 前端
汽配领域知产保护分析平台
"""

import streamlit as st
import sys
import os
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services.upload_service import UploadService, TableFormatError
from services.clean_service import CleanService
from services.extract_service import ExtractService
from services.score_service import ScoreService
from services.suspicion_detector import SuspicionDetector
from services.case_service import CaseService
from services.role_detector import RoleDetector
from services.amount_calculator import AmountCalculator
from services.evidence_analyzer import EvidenceAnalyzer
from services.relation_analyzer import RelationAnalyzer
from utils.report_generator import ReportGenerator
from utils.exporter import Exporter
from utils.masking import MaskingTool
from utils.keywords import keyword_library

st.set_page_config(page_title="火眼智擎 - 汽配知产保护分析", layout="wide")

# 初始化session state
if "case_data" not in st.session_state:
    st.session_state.case_data = None
if "transactions" not in st.session_state:
    st.session_state.transactions = []
if "communications" not in st.session_state:
    st.session_state.communications = []
if "logistics" not in st.session_state:
    st.session_state.logistics = []
if "persons" not in st.session_state:
    st.session_state.persons = []
if "suspicious_clues" not in st.session_state:
    st.session_state.suspicious_clues = []

# 标题
st.title("火眼智擎 - 汽配领域知产保护分析平台")
st.markdown("---")

# 侧边栏
page = st.sidebar.selectbox(
    "功能导航",
    [
        "📊 数据看板",
        "📁 数据导入",
        "📋 案件管理",
        "🔍 智能证据解析",
        "🔗 关联分析",
        "📋 台账",
    ],
)

# ==================== 数据看板 ====================
if page == "📊 数据看板":
    st.header("数据看板")

    # 统计卡片
    col1, col2, col3, col4 = st.columns(4)

    # 案件数：如果有导入数据则为1，否则为0
    case_count = (
        1
        if (
            st.session_state.transactions
            or st.session_state.communications
            or st.session_state.logistics
        )
        else 0
    )
    clue_count = (
        len(st.session_state.suspicious_clues)
        if st.session_state.suspicious_clues
        else 0
    )
    total_amount = (
        sum(float(t.get("amount", 0)) for t in st.session_state.transactions)
        if st.session_state.transactions
        else 0
    )
    person_count = len(st.session_state.persons) if st.session_state.persons else 0

    col1.metric("案件总数", case_count)
    col2.metric("可疑线索数", clue_count)
    col3.metric("累计涉案金额", f"{total_amount:.0f}元")
    col4.metric("重点布控人员", person_count)

    st.markdown("---")

    # 图表区域
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("品牌分布")
        if st.session_state.transactions:
            # 简单统计
            brands = ["博世", "奥迪", "奔驰", "宝马", "米其林"]
            brand_data = [30, 20, 15, 15, 20]
            st.bar_chart({"品牌": brands, "数量": brand_data})
        else:
            st.info("请先导入数据")

    with col2:
        st.subheader("金额走势")
        months = ["1月", "2月", "3月", "4月", "5月", "6月"]
        amounts = [10000, 25000, 30000, 45000, 38000, 50000]
        st.line_chart({"月份": months, "金额": amounts})

# ==================== 数据导入 ====================
elif page == "📁 数据导入":
    st.header("数据导入")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("资金流水")
        trans_file = st.file_uploader("上传资金流水CSV", type=["csv"], key="trans")

    with col2:
        st.subheader("通讯记录")
        comm_file = st.file_uploader("上传通讯记录CSV", type=["csv"], key="comm")

    with col3:
        st.subheader("物流记录")
        log_file = st.file_uploader("上传物流记录CSV", type=["csv"], key="log")

    case_id = st.number_input("案件ID", min_value=1, value=1)

    if st.button("导入并分析", type="primary"):
        temp_dir = os.path.join(os.path.dirname(__file__), "data", "temp")
        os.makedirs(temp_dir, exist_ok=True)

        trans_path = None
        comm_path = None
        log_path = None

        try:
            with st.spinner("导入中..."):
                # 导入资金流水
                if trans_file:
                    trans_path = os.path.join(temp_dir, trans_file.name)
                    with open(trans_path, "wb") as f:
                        f.write(trans_file.getbuffer())
                    st.session_state.transactions = UploadService.parse_transactions(
                        trans_path, case_id=case_id
                    )
                    st.session_state.transactions = CleanService.clean_transactions(
                        st.session_state.transactions
                    )

                # 导入通讯记录
                if comm_file:
                    comm_path = os.path.join(temp_dir, comm_file.name)
                    with open(comm_path, "wb") as f:
                        f.write(comm_file.getbuffer())
                    st.session_state.communications = (
                        UploadService.parse_communications(comm_path, case_id=case_id)
                    )
                    st.session_state.communications = CleanService.clean_communications(
                        st.session_state.communications
                    )

                # 导入物流记录
                if log_file:
                    log_path = os.path.join(temp_dir, log_file.name)
                    with open(log_path, "wb") as f:
                        f.write(log_file.getbuffer())
                    st.session_state.logistics = UploadService.parse_logistics(
                        log_path, case_id=case_id
                    )
                    st.session_state.logistics = CleanService.clean_logistics(
                        st.session_state.logistics
                    )

            with st.spinner("执行智能分析..."):
                # 自动化抽取
                extract_result = ExtractService.extract_from_files(
                    transaction_file=trans_path,
                    communication_file=comm_path,
                    logistics_file=log_path,
                    case_id=case_id,
                )
                st.session_state.persons = extract_result.get("persons", [])
                st.session_state.case_data = extract_result

                # 可疑线索检测
                if st.session_state.communications:
                    st.session_state.suspicious_clues = (
                        SuspicionDetector.detect_from_communication(
                            case_id, st.session_state.communications
                        )
                    )

            st.success("导入并分析完成！")
        except TableFormatError as e:
            st.error(f"导入失败：{str(e)}")
            st.info("请按系统模板字段上传，确保表头列名与模板一致。")
        except Exception as e:
            st.error(f"导入失败：{str(e)}")

    # 显示导入结果
    if st.session_state.transactions:
        st.markdown("---")
        st.subheader("资金流水预览")
        df_trans = pd.DataFrame(st.session_state.transactions)
        st.dataframe(df_trans.head(20), use_container_width=True)

    if st.session_state.communications:
        st.markdown("---")
        st.subheader("通讯记录预览")
        df_comm = pd.DataFrame(st.session_state.communications)
        st.dataframe(df_comm.head(20), use_container_width=True)

    if st.session_state.logistics:
        st.markdown("---")
        st.subheader("物流记录预览")
        df_log = pd.DataFrame(st.session_state.logistics)
        st.dataframe(df_log.head(20), use_container_width=True)

    if st.session_state.persons:
        st.markdown("---")
        st.subheader("人员档案")
        df_persons = pd.DataFrame(st.session_state.persons)
        st.dataframe(df_persons, use_container_width=True)

    if st.session_state.suspicious_clues:
        st.markdown("---")
        st.subheader("可疑线索")
        for i, clue in enumerate(st.session_state.suspicious_clues):
            with st.expander(
                f"线索 {i+1}: {clue.get('clue_type')} (评分:{clue.get('score')})"
            ):
                st.markdown(f"**证据原文**: {clue.get('evidence_text')}")
                st.markdown(
                    f"**命中关键词**: {', '.join(clue.get('hit_keywords', []))}"
                )
                st.markdown(f"**涉嫌罪名**: {clue.get('crime_type')}")

# ==================== 案件管理 ====================
elif page == "📋 案件管理":
    st.header("案件管理")

    # 搜索栏
    col1, col2, col3 = st.columns(3)
    with col1:
        search_case_no = st.text_input("案件编号")
    with col2:
        search_name = st.text_input("嫌疑人姓名")
    with col3:
        search_brand = st.text_input("涉案品牌")

    if st.button("搜索"):
        st.info("搜索功能需要后端支持")

    st.markdown("---")

    # 案件列表
    st.subheader("案件列表")

    if st.session_state.transactions:
        # 显示统计信息作为"案件"
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(
                "涉案金额",
                f"{sum(float(t.get('amount', 0)) for t in st.session_state.transactions):.0f}元",
            )
        with col2:
            st.metric("交易笔数", len(st.session_state.transactions))
        with col3:
            st.metric("嫌疑人数", len(st.session_state.persons))

        st.markdown("---")

        # 交易记录表格
        st.subheader("交易记录")
        if st.session_state.transactions:
            trans_data = []
            for t in st.session_state.transactions:
                amount = float(t.get("amount", 0))
                trans_data.append(
                    {
                        "日期": t.get("transaction_time", ""),
                        "打款方": MaskingTool.mask_name(t.get("payer", "")),
                        "收款方": MaskingTool.mask_name(t.get("payee", "")),
                        "金额": (
                            f"{amount:.0f}元" if amount > 10000 else f"{amount:.2f}元"
                        ),
                        "支付方式": t.get("payment_method", ""),
                        "备注": t.get("remark", ""),
                    }
                )
            df = pd.DataFrame(trans_data)
            st.dataframe(df, use_container_width=True)

        # 通讯记录（带高亮）
        st.markdown("---")
        st.subheader("聊天记录")

        if st.session_state.communications:
            for comm in st.session_state.communications:
                content = comm.get("content", "")
                # 检测敏感词
                matches = keyword_library.search(content)
                if matches:
                    # 高亮显示
                    highlighted = content
                    for m in matches:
                        highlighted = highlighted.replace(
                            m["word"],
                            f"<span style='background-color:yellow'>**{m['word']}**</span>",
                        )
                    st.markdown(
                        f"**{comm.get('initiator', '')} → {comm.get('receiver', '')}**"
                    )
                    st.markdown(highlighted, unsafe_allow_html=True)
                    st.markdown(f"*{comm.get('communication_time', '')}*")
                    st.markdown("---")

        # 生成报告按钮
        st.markdown("---")
        if st.button("生成Word分析报告", type="primary"):
            if st.session_state.case_data:
                report_path = ReportGenerator.generate_simple_report(
                    case_no="CASE001",
                    suspect_name="涉案人员",
                    brand="涉案品牌",
                    amount=sum(
                        float(t.get("amount", 0)) for t in st.session_state.transactions
                    ),
                    clue_count=len(st.session_state.suspicious_clues),
                    evidence_count=len(st.session_state.communications),
                )
                st.success(f"报告已生成: {report_path}")

# ==================== 智能证据解析 ====================
elif page == "🔍 智能证据解析":
    st.header("智能证据解析")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("证据输入")
        evidence_text = st.text_area(
            "输入聊天内容", height=150, placeholder="例如：这批货你别声张，不是原厂的"
        )
        product = st.text_input("产品名称", placeholder="例如：奥迪A4L轮毂")
        quote_price = st.number_input("报价（元）", min_value=0, value=280)
        reference_price = st.number_input("参考价（元）", min_value=0, value=600)

        if st.button("开始分析", type="primary"):
            if evidence_text:
                with st.spinner("分析中..."):
                    # 价格异常判定
                    price_ratio = (
                        quote_price / reference_price if reference_price > 0 else 0
                    )
                    is_anomaly = AmountCalculator.is_price_anomaly(
                        quote_price, reference_price
                    )

                    # 主观明知评分
                    score_result = ScoreService.analyze_text(evidence_text)
                    crime_type = ScoreService.get_crime_type(score_result["matches"])

                    # 关键主体提取
                    matches = keyword_library.search(evidence_text)
                    hit_keywords = [m["word"] for m in matches]

                    # 推断角色
                    role = RoleDetector.detect_role_by_keywords(evidence_text)

                    # 存储结果到session
                    st.session_state.analysis_result = {
                        "price_ratio": price_ratio,
                        "is_anomaly": is_anomaly,
                        "score": score_result["score"],
                        "level": score_result["level"],
                        "crime_type": crime_type,
                        "hit_keywords": hit_keywords,
                        "evidence_text": evidence_text,
                        "role": role,
                        "product": product,
                        "quote_price": quote_price,
                        "reference_price": reference_price,
                    }

    with col2:
        st.subheader("分析结果")

        if "analysis_result" in st.session_state:
            result = st.session_state.analysis_result

            # 卡片1 - 价格异常判定
            st.markdown("### 卡片1 - 价格异常判定")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**产品**: {result.get('product', 'N/A')}")
                st.markdown(f"**报价**: {result.get('quote_price')}元")
            with col_b:
                st.markdown(f"**参考价**: {result.get('reference_price')}元")
                st.markdown(f"**低于参考价**: {result.get('price_ratio')*100:.0f}%")

            if result.get("is_anomaly"):
                st.error("⚠️ 价格异常 - 低于正品50%以上")
            else:
                st.success("✓ 价格正常")

            st.markdown("---")

            # 卡片2 - 主观明知证据
            st.markdown("### 卡片2 - 主观明知证据")
            st.markdown(f"**原文引用**: 「{result.get('evidence_text', '')}」")
            st.markdown(
                f"**命中关键词**: {', '.join(result.get('hit_keywords', [])) if result.get('hit_keywords') else '无'}"
            )
            st.markdown(f"**评分**: {result.get('score')}分 ({result.get('level')})")

            st.markdown("---")

            # 卡片3 - 关键主体提取
            st.markdown("### 卡片3 - 关键主体提取")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**角色**: {result.get('role', 'N/A')}")
            with col_b:
                st.markdown(f"**涉嫌罪名**: {result.get('crime_type', '待定')}")

            st.markdown("---")

            # 底部按钮
            col1, col2 = st.columns(2)
            with col1:
                if st.button("生成初步分析报告"):
                    st.info("报告生成功能")
            with col2:
                if st.button("转入关联图谱分析"):
                    st.info("跳转关联分析页面")
        else:
            st.info("请输入证据内容并点击「开始分析」")

# ==================== 关联分析 ====================
elif page == "🔗 关联分析":
    st.header("关联分析")

    tab1, tab2 = st.tabs(["上下游关系图", "跨案关联拓扑"])

    with tab1:
        st.subheader("单案上下游产业链")

        if st.session_state.case_data:
            # 显示上下游统计
            persons = st.session_state.case_data.get("persons", [])
            hidden_sources = st.session_state.case_data.get("hidden_sources", [])

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("节点数", len(persons) + len(hidden_sources))
            with col2:
                st.metric("关系链路", len(st.session_state.transactions))
            with col3:
                st.metric("供应商数", len(hidden_sources))
            with col4:
                st.metric(
                    "买家数",
                    len([p for p in persons if "下游" in str(p.get("role", ""))]),
                )

            st.markdown("---")

            # 上游供货商
            if hidden_sources:
                st.markdown("### 上游供货商")
                for source in hidden_sources:
                    with st.expander(f"📍 {source.get('address', '未知地址')}"):
                        st.markdown(f"**发货次数**: {source.get('shipment_count', 0)}")
                        st.markdown(
                            f"**发件人**: {', '.join(source.get('senders', []))}"
                        )

            # 核心嫌疑人
            if persons:
                st.markdown("### 核心嫌疑人")
                for person in persons[:5]:
                    with st.expander(f"👤 {person.get('name', '未知')}"):
                        st.markdown(f"**角色**: {person.get('role', '未知')}")
                        st.markdown(
                            f"**涉案金额**: {person.get('illegal_business_amount', 0)}元"
                        )
                        st.markdown(f"**关联案件**: {person.get('linked_cases', 0)}个")
        else:
            st.info("请先在「数据导入」页面导入数据")

    with tab2:
        st.subheader("跨案关联拓扑")

        if st.session_state.persons:
            # 跨案统计
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("节点总数", len(st.session_state.persons))
            with col2:
                st.metric("关系链路", len(st.session_state.transactions))
            with col3:
                st.metric(
                    "关键节点",
                    len(
                        [
                            p
                            for p in st.session_state.persons
                            if p.get("role") == "核心嫌疑人"
                        ]
                    ),
                )
            with col4:
                st.metric("涉案案件", 1)

            st.markdown("---")

            # 风险人员列表
            st.markdown("### 风险人员")
            for person in st.session_state.persons:
                role = person.get("role", "")
                score = person.get("subjective_knowledge_score", 0)

                # 风险标签
                risk_tags = []
                if score >= 8:
                    risk_tags.append("🔴 高危")
                elif score >= 5:
                    risk_tags.append("🟡 中危")

                if role in ["上游供货商", "核心嫌疑人"]:
                    risk_tags.append("⚠️ 重点关注")

                with st.expander(f"{' '.join(risk_tags)} {person.get('name', '未知')}"):
                    st.markdown(f"**角色**: {role}")
                    st.markdown(f"**主观明知评分**: {score}")
                    st.markdown(
                        f"**涉案金额**: {person.get('illegal_business_amount', 0)}元"
                    )
                    st.markdown(f"**关联案件**: {person.get('linked_cases', 0)}个")

                    if st.button(
                        f"查看完整证据链", key=f"evidence_{person.get('name')}"
                    ):
                        st.info("证据链详情")
        else:
            st.info("请先在「数据导入」页面导入数据")

# ==================== 数据台账 ====================
elif page == "📋 台账":
    st.header("数据台账")

    tab1, tab2, tab3 = st.tabs(["人员台账", "交易台账", "证据清单"])

    with tab1:
        st.subheader("人员台账")

        if st.session_state.persons:
            # 人员台账表格
            person_data = []
            for p in st.session_state.persons:
                person_data.append(
                    {
                        "姓名": MaskingTool.mask_name(p.get("name", "")),
                        "角色": p.get("role", "未知"),
                        "涉案金额": f"{p.get('illegal_business_amount', 0)}元",
                        "关联案件数": p.get("linked_cases", 0),
                        "联系电话": MaskingTool.mask_phone("13812345678"),  # 示例脱敏
                    }
                )
            df = pd.DataFrame(person_data)
            st.dataframe(df, use_container_width=True)

            # 导出按钮
            col1, col2 = st.columns([6, 1])
            with col2:
                if st.button("导出CSV"):
                    csv_path = Exporter.export_persons(st.session_state.persons)
                    st.success(f"已导出: {csv_path}")
        else:
            st.info("暂无人员数据")

    with tab2:
        st.subheader("交易台账")

        if st.session_state.transactions:
            trans_data = []
            for i, t in enumerate(st.session_state.transactions):
                trans_data.append(
                    {
                        "交易编号": f"TXN{str(i+1).zfill(6)}",
                        "打款方": MaskingTool.mask_name(t.get("payer", "")),
                        "收款方": MaskingTool.mask_name(t.get("payee", "")),
                        "产品": (
                            t.get("remark", "").split()[0] if t.get("remark") else "N/A"
                        ),
                        "金额": f"{t.get('amount', 0)}元",
                        "日期": t.get("transaction_time", ""),
                        "案件编号": "CASE001",
                    }
                )
            df = pd.DataFrame(trans_data)
            st.dataframe(df, use_container_width=True)

            # 导出按钮
            col1, col2 = st.columns([6, 1])
            with col2:
                if st.button("导出CSV", key="export_trans"):
                    csv_path = Exporter.export_transactions(
                        st.session_state.transactions
                    )
                    st.success(f"已导出: {csv_path}")
        else:
            st.info("暂无交易数据")

    with tab3:
        st.subheader("证据清单")

        if st.session_state.suspicious_clues:
            evidence_data = []
            for clue in st.session_state.suspicious_clues:
                evidence_data.append(
                    {
                        "类型": clue.get("clue_type", "未知"),
                        "证据原文": clue.get("evidence_text", "")[:50] + "...",
                        "命中关键词": ", ".join(clue.get("hit_keywords", [])),
                        "评分": clue.get("score", 0),
                        "涉嫌罪名": clue.get("crime_type", "待定"),
                        "严重程度": clue.get("severity_level", "未知"),
                    }
                )
            df = pd.DataFrame(evidence_data)
            st.dataframe(df, use_container_width=True)

            # 导出按钮
            col1, col2 = st.columns([6, 1])
            with col2:
                if st.button("导出CSV", key="export_evidence"):
                    st.info("证据清单导出")
        else:
            st.info("暂无证据数据")

# 底部信息
st.markdown("---")
st.markdown("火眼智擎 v1.0 - 汽配领域知产保护分析平台 | © 2026")
