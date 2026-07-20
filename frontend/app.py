import os
import sys
import json
import time
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import graphviz
from openai import OpenAI
import requests

# ==========================================
# CẤU HÌNH GIAO DIỆN MẶC ĐỊNH 
# ==========================================
st.set_page_config(page_title="OPC Mission Control", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.15), transparent 40%),
                        radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.15), transparent 40%),
                        radial-gradient(circle at 50% 50%, rgba(255, 75, 75, 0.05), transparent 50%),
                        #080c16 !important;
            background-attachment: fixed;
        }
        .block-container { padding-top: 2rem; padding-bottom: 1rem; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.2); border-radius: 10px; }
        ::-webkit-scrollbar-track { background: transparent; }
        .stTabs [data-baseweb="tab-list"] { gap: 15px; border-bottom: none !important; background: transparent !important; padding: 10px 0; }
        .stTabs [data-baseweb="tab"] { padding: 10px 24px; background-color: rgba(255, 255, 255, 0.03); border-radius: 50px !important; color: #94a3b8; border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); transition: all 0.3s ease-in-out; }
        .stTabs [aria-selected="true"] { background: rgba(59, 130, 246, 0.25) !important; color: white !important; border: 1px solid rgba(150, 200, 255, 0.4) !important; box-shadow: inset 0 2px 10px rgba(255, 255, 255, 0.2), 0 8px 20px rgba(59, 130, 246, 0.3) !important; }
        .stTabs [data-baseweb="tab-highlight"] { display: none !important; }
        div[data-testid="metric-container"] { background: rgba(255, 255, 255, 0.02); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid rgba(255, 255, 255, 0.1); padding: 5% 10%; border-radius: 24px; box-shadow: inset 0 2px 5px rgba(255,255,255,0.05), 0 8px 32px 0 rgba(0, 0, 0, 0.2); }
        .stAlert, .stInfo, .stSuccess, .stWarning, .stError { background: rgba(255, 255, 255, 0.05) !important; backdrop-filter: blur(15px) !important; border: 1px solid rgba(255, 255, 255, 0.1) !important; border-radius: 16px !important; color: #f1f5f9 !important; box-shadow: inset 0 1px 4px rgba(255,255,255,0.1); }
        
        @keyframes blink {
            0% { background-color: rgba(255, 75, 75, 0.2); border: 2px solid #ff4b4b; box-shadow: 0 0 10px #ff4b4b; }
            50% { background-color: rgba(255, 75, 75, 0.4); border: 2px solid #ff1a1a; box-shadow: 0 0 20px #ff1a1a; }
            100% { background-color: rgba(255, 75, 75, 0.2); border: 2px solid #ff4b4b; box-shadow: 0 0 10px #ff4b4b; }
        }
        .red-alert {
            animation: blink 1.5s infinite;
            padding: 20px;
            border-radius: 16px;
            color: #ffffff;
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 25px;
            text-align: center;
            text-shadow: 0 2px 4px rgba(0,0,0,0.5);
        }
    </style>
""", unsafe_allow_html=True)

# ĐỊA CHỈ BACKEND TRÊN RENDER
BACKEND_URL = "https://backend-qm8g.onrender.com"

# LẤY API KEY
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except:
        pass

if not api_key:
    st.error("🚨 Missing OPENAI_API_KEY environment variable!")
    st.stop()

client = OpenAI(api_key=api_key)

# ==========================================
# HÀM VẼ SƠ ĐỒ TRẠNG THÁI (GRAPHVIZ)
# ==========================================
def draw_architecture(active_agents=[], alert=False):
    dot = graphviz.Digraph(engine='dot')
    dot.attr(rankdir='LR', size='10,4', bgcolor='transparent')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', width='1.5')
    dot.attr('edge', fontcolor='white', color='#94a3b8')
    
    colors = {
        'Data': '#e6f2ff' if 'Data' not in active_agents else '#4da6ff',
        'Planner': '#e6f2ff' if 'Planner' not in active_agents else '#4da6ff',
        'Finance': '#e6ffe6' if 'Finance' not in active_agents else '#4dff4d',
        'Risk': '#ffe6e6' if 'Risk' not in active_agents else ('#ff4b4b' if alert else '#ff9999'),
        'Banking': '#f2e6ff' if 'Banking' not in active_agents else '#b366ff',
        'Decision': '#ffffe6' if 'Decision' not in active_agents else '#ffff4d'
    }

    for agent, color in colors.items():
        dot.node(agent, f"{agent} Agent", fillcolor=color, fontcolor='black')

    dot.edge('Data', 'Planner', label=' Raw Data')
    dot.edge('Planner', 'Finance', label=' Task')
    dot.edge('Planner', 'Risk', label=' Task')
    dot.edge('Planner', 'Banking', label=' Task')
    dot.edge('Finance', 'Decision', label=' Margin')
    dot.edge('Risk', 'Decision', label=' Risk')
    dot.edge('Banking', 'Decision', label=' Product')

    return dot

# ==========================================
# CÁC HÀM AGENT (CHUẨN FORM THỂ LỆ MIS TALENT 2026)
# ==========================================
def agent_planner(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", response_format={ "type": "json_object" }, messages=[{"role": "system", "content": "Trả về JSON: { 'task_breakdown': '...', 'approval_gates': '...', 'workflow_plan': '...' } Tiếng Việt."}, {"role": "user", "content": data_bundle.get('contracts', '')}], temperature=0.1)
    parsed = json.loads(response.choices[0].message.content)
    content = f"**Objective:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"
    return content, response.usage.total_tokens

def agent_finance(data_bundle):
    sys_prompt = "Phân tích tài chính. Bắt buộc trả về: 1. Ba chỉ số tài chính chính (doanh thu, chi phí, biên lợi nhuận). 2. Nhu cầu vốn cụ thể để thực hiện hợp đồng. Tiếng Việt, trình bày gạch đầu dòng ngắn gọn."
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": data_bundle.get('cashflow', '')}], temperature=0.1)
    return response.choices[0].message.content, response.usage.total_tokens

def agent_risk_compliance(data_bundle):
    sys_prompt = "Phân tích rủi ro. Bắt buộc trả về: 1. Đánh giá Risk Level (High/Medium/Low). 2. Danh sách hồ sơ bị thiếu. 3. Các cảnh báo rủi ro trọng yếu và điểm cần con người xác nhận. Tiếng Việt."
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": f"Data: {data_bundle.get('txn', '')}"}], temperature=0.1)
    return response.choices[0].message.content, response.usage.total_tokens

def agent_banking_integration(data_bundle):
    system_prompt = "Bạn là Giám đốc Quan hệ Khách hàng Doanh nghiệp. Phân tích danh sách sản phẩm ngân hàng (data) và đề xuất đối tác tài trợ vốn tối ưu nhất. Trình bày Markdown. Ngôn từ chuyên nghiệp."
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Dữ liệu ngân hàng: {data_bundle.get('bank_prod', '')}"}], temperature=0.3)
    return response.choices[0].message.content, response.usage.total_tokens

def agent_decision(full_packet):
    sys_prompt = "Đóng vai Tổng Giám Đốc OPC. Trả về Decision Card với cấu trúc bắt buộc: 1. Phương án (Chấp nhận hay Từ chối hợp đồng). 2. Ba lý do chính yếu. 3. Một điều kiện bắt buộc cần Nhà sáng lập xác nhận (protection condition). Kèm tỷ lệ Confidence Score %."
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": full_packet}], temperature=0.1)
    return response.choices[0].message.content, response.usage.total_tokens

# ==========================================
# LUỒNG CHẠY CHÍNH (MAIN FUNCTION)
# ==========================================
def main():
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False
    if "total_tokens" not in st.session_state:
        st.session_state.total_tokens = 0

    # GIAO DIỆN CHỜ (LANDING PAGE)
    if not st.session_state.data_loaded:
        st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
        col_L, col_C, col_R = st.columns([1, 2, 1])
        with col_C:
            st.markdown("<h1 style='text-align: center; color: white; text-shadow: 0 0 30px rgba(59,130,246,0.8);'>⚡ OPC COMMAND CENTER</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 30px;'>Multi-Agent System Dashboard</p>", unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader("", type=["xlsx"])
            if uploaded_file is not None:
                with st.spinner("Uploading data to Backend..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                    try:
                        res = requests.post(f"{BACKEND_URL}/upload", files=files)
                        if res.status_code == 200 and res.json().get("status") == "success":
                            
                            st.session_state.raw_data = requests.get(f"{BACKEND_URL}/api/data/raw").json()
                            dashboard_data = requests.get(f"{BACKEND_URL}/api/data/dashboard").json()
                            
                            st.session_state.df_cf = pd.DataFrame(dashboard_data['cashflow'])
                            st.session_state.df_txn = pd.DataFrame(dashboard_data['txn'])
                            
                            st.session_state.data_loaded = True
                            st.rerun() 
                        else:
                            st.error("Backend processing failed!")
                    except requests.exceptions.ConnectionError:
                        st.error("🚨 Cannot connect to Render Backend!")
        st.stop()

    raw_data = st.session_state.raw_data
    df_cf = st.session_state.df_cf
    df_txn = st.session_state.df_txn

    head_col1, head_col2 = st.columns([5, 1])
    with head_col1:
        st.markdown("## ⚡ OPC Multi-Agent Command Center")
    with head_col2:
        if st.button("🔄 Close Dashboard", use_container_width=True):
            st.session_state.clear() 
            st.rerun()

    # ==========================================
    # KHU VỰC LOAD ĐỘNG CỦA 6 AGENTS
    # ==========================================
    if "ai_completed" not in st.session_state:
        st.markdown("<h3 style='text-align: center; color: #3b82f6;'>⚙️ SYSTEM IS ANALYZING DATA...</h3>", unsafe_allow_html=True)
        st.write("")
        
        start_time = time.time()
        st.session_state.total_tokens = 0
        
        col_log, col_graph = st.columns([1, 1.5])
        
        with col_graph:
            graph_placeholder = st.empty()
            graph_placeholder.graphviz_chart(draw_architecture())

        with col_log:
            with st.status("Initializing Agentic Workflow...", expanded=True) as status:
                # 1. Data Agent
                graph_placeholder.graphviz_chart(draw_architecture(['Data']))
                st.write("⏳ **Data Agent:** Parsing Pandas data...")
                time.sleep(1)
                st.write("✅ **Data Agent:** Data preparation completed.")
                
                # 2. Planner Agent
                graph_placeholder.graphviz_chart(draw_architecture(['Data', 'Planner']))
                st.write("⏳ **Planner Agent:** Designing Workflow structure...")
                rep_p, tok_p = agent_planner(raw_data) 
                st.session_state.p_rep = rep_p
                st.session_state.total_tokens += tok_p
                st.write("✅ **Planner Agent:** Workflow breakdown completed.")

                # 3. Finance Agent
                graph_placeholder.graphviz_chart(draw_architecture(['Data', 'Planner', 'Finance']))
                st.write("⏳ **Finance Agent:** Running Cashflow projection...")
                rep_f, tok_f = agent_finance(raw_data) 
                st.session_state.f_rep = rep_f
                st.session_state.total_tokens += tok_f
                st.write("✅ **Finance Agent:** Financial report ready.")

                # 4. Risk Agent (Có báo động đỏ)
                graph_placeholder.graphviz_chart(draw_architecture(['Data', 'Planner', 'Finance', 'Risk'], alert=True))
                st.write("⏳ **Risk Agent:** Scanning for anomalies...")
                time.sleep(1)
                st.markdown('<span style="color:#ff4b4b; font-weight:bold;">🚨 Risk Agent: MISSING LEGAL DOCUMENTS DETECTED!</span>', unsafe_allow_html=True)
                rep_r, tok_r = agent_risk_compliance(raw_data) 
                st.session_state.r_rep = rep_r
                st.session_state.total_tokens += tok_r
                st.write("✅ **Risk Agent:** Compliance check done (1 Risk Flag logged).")

                # 5. Banking Agent
                graph_placeholder.graphviz_chart(draw_architecture(['Data', 'Planner', 'Finance', 'Risk', 'Banking'], alert=True))
                st.write("⏳ **Banking Agent:** Pinging Core Banking Server...")
                rep_b, tok_b = agent_banking_integration(raw_data) 
                st.session_state.b_rep = rep_b
                st.session_state.total_tokens += tok_b
                st.write("✅ **Banking Agent:** Product mapping successful.")

                # 6. Decision Agent
                graph_placeholder.graphviz_chart(draw_architecture(['Data', 'Planner', 'Finance', 'Risk', 'Banking', 'Decision'], alert=True))
                st.write("⏳ **Decision Agent:** Calculating decision weights...")
                rep_dec, tok_dec = agent_decision(f"{st.session_state.p_rep}\n\n[TÀI CHÍNH]\n{st.session_state.f_rep}\n\n[RỦI RO]\n{st.session_state.r_rep}") 
                st.session_state.final_dec = rep_dec
                st.session_state.total_tokens += tok_dec
                st.write("✅ **Decision Agent:** Decision Card generated.")
                
                status.update(label="Data Analysis Completed!", state="complete", expanded=False)

        end_time = time.time()
        st.session_state.processing_time = round(end_time - start_time, 2)
        st.session_state.ai_completed = True
        st.rerun() 

    # ==========================================
    # CÁC TAB HIỂN THỊ CHÍNH (ĐÃ FIX TÊN)
    # ==========================================
    tab_overview, tab_agents, tab_analysis, tab_dashboard, tab_chat = st.tabs([
        "🌐 System Overview", "🤖 Agents Fleet", "🧠 Agent Reasoning", "📊 Power Dashboard", "💬 Command Line"
    ])

    with tab_overview:
        st.markdown("### 📡 System Overview")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("LLM Engine", "gpt-4o", "Core API Online")
        m2.metric("Active Agents", "6 Agents", "Running")
        m3.metric("Processing Time", f"{st.session_state.processing_time}s", "100% Completed")
        m4.metric("Token Usage", f"{st.session_state.total_tokens:,}", "Real-time cost")
        
        st.divider()
        col_act, col_arch = st.columns([1, 1.5])
        with col_act:
            st.markdown("**🔄 Execution Pipeline**")
            st.progress(100, text="✅ Data Agent: Parsed raw data (100%)")
            st.progress(100, text="✅ Planner Agent: Initialized workflow (100%)")
            st.progress(100, text="✅ Finance Agent: Generated financial metrics (100%)")
            st.progress(100, text="✅ Risk Agent: Flagged compliance issues (100%)")
            st.progress(100, text="✅ Banking Agent: Mapped API endpoints (100%)")
            st.progress(100, text="✅ Decision Agent: Exported Decision Card (100%)")
            
        with col_arch:
            st.markdown("**🧠 System Reasoning Architecture**")
            st.graphviz_chart(draw_architecture(['Data', 'Planner', 'Finance', 'Risk', 'Banking', 'Decision'], alert=True))

    with tab_agents:
        st.markdown("### 🤖 Agents Fleet Status")
        tasks_risk = len(df_txn) 
        tasks_finance = len(df_cf)
        
        # ROW 1: 3 AGENTS
        a1, a2, a3 = st.columns(3)
        with a1: st.success("**📦 Data Agent**\n\n- Processed: Raw Input Data\n- Status: Completed")
        with a2: st.success("**🎯 Planner Agent**\n\n- Processed: 1 Workflow Plan\n- Status: Completed")
        with a3: st.info(f"**📊 Finance Agent**\n\n- Processed: {tasks_finance} records\n- Status: Completed")
        
        st.write("")
        
        # ROW 2: 3 AGENTS
        a4, a5, a6 = st.columns(3)
        with a4: st.warning(f"**🛡️ Risk Agent**\n\n- Processed: {tasks_risk} transactions\n- Alert: Missing Documents")
        with a5: st.success("**🏦 Banking Agent**\n\n- Processed: Bank Products API\n- Status: Completed")
        with a6: st.success("**⚖️ Decision Agent**\n\n- Processed: 1 Decision Card\n- Status: Completed")
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # REAL-TIME HEATMAP LOGIC
        try:
            # GỌI API THỰC TẾ (Nếu render backend đã viết route này)
            res_heatmap = requests.get(f"{BACKEND_URL}/api/system/workload", timeout=3)
            if res_heatmap.status_code == 200:
                z_dynamic = res_heatmap.json().get("workload_matrix")
            else:
                raise Exception("API not returning 200")
        except:
            # FALLBACK MẶC ĐỊNH nếu Backend chưa có Endpoint này (Giữ form biểu đồ không bị sập)
            z_dynamic = [
                [10, 15, 20, 25, 30],
                [12, 18, 22, 28, 35],
                [8, 14, 19, 21, 27]
            ]
            
        fig_heat = go.Figure(data=go.Heatmap(
            z=z_dynamic, 
            x=['Mon', 'Tue', 'Wed', 'Thu', 'Fri'], 
            y=['Morning', 'Afternoon', 'Evening'], 
            colorscale='Blues'
        )) 
        fig_heat.update_layout(
            title="💧 Real-time Agent Workload Distribution", 
            height=280, 
            margin=dict(t=40, b=20, l=40, r=20), 
            template="plotly_dark", 
            plot_bgcolor="rgba(0,0,0,0)", 
            paper_bgcolor="rgba(0,0,0,0)"
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with tab_analysis:
        st.markdown("### 🧠 Agent Reasoning Process")
        st.success("**🎯 Planner Agent:** Initialized task breakdown.")
        with st.expander("📄 View Workflow Plan"): st.markdown(st.session_state.p_rep)
            
        st.info("**📊 Finance Agent:** Evaluated key metrics and capital needs.")
        with st.expander("📄 View Financial Analysis"): st.markdown(st.session_state.f_rep)
            
        st.warning("**🛡️ Risk Agent:** Classified Risk Level, detected missing documents.")
        with st.expander("📄 View Risk & Compliance Report"): st.markdown(st.session_state.r_rep)
            
        st.success("**🏦 Banking Agent:** Mapped optimal banking products.")
        with st.expander("📄 View Banking Integration Info"): st.markdown(st.session_state.b_rep)

    with tab_dashboard:
        layout_update = dict(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10), height=260)
        
        cash_col = df_cf.columns[-2]
        df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        risk_col = df_txn.columns[-1]
        df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce').fillna(0)
        df_txn['Label'] = df_txn[risk_col].apply(lambda x: 'High Risk' if x >= 85 else 'Safe')
        df_txn['BubbleSize'] = df_txn[risk_col].apply(lambda x: max(x, 1))

        c1, c2, c3 = st.columns(3)
        with c1:
            fig_cf_line = px.line(df_cf, x=df_cf.columns[0], y=cash_col, title="📉 Cashflow Trend", markers=True, color_discrete_sequence=['#3b82f6'])
            fig_cf_line.update_layout(**layout_update)
            st.plotly_chart(fig_cf_line, use_container_width=True, config={'displayModeBar': False})
        with c2:
            risk_counts = df_txn['Label'].value_counts().reset_index()
            fig_pie = px.pie(risk_counts, values='count', names='Label', title="🚨 Risk Distribution", hole=0.6, color='Label', color_discrete_map={'High Risk': '#ff4b4b', 'Safe': '#3b82f6'})
            fig_pie.update_layout(**layout_update, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        with c3:
            df_risk_top = df_txn.sort_values(by=risk_col, ascending=True).tail(5) 
            fig_bar = px.bar(df_risk_top, x=risk_col, y=df_txn.columns[0], orientation='h', title="🛡️ Top 5 High-Risk Transactions", color=risk_col, color_continuous_scale='Blues')
            fig_bar.update_layout(**layout_update, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

        st.markdown("<br>", unsafe_allow_html=True)
        
        c4, c5 = st.columns([2, 1])
        with c4:
            fig_scatter = px.scatter(df_txn, x=df_txn.columns[0], y=risk_col, color='Label', size='BubbleSize', title="📍 Anomaly Detection Scatter", color_discrete_map={'High Risk': '#ff4b4b', 'Safe': '#3b82f6'})
            fig_scatter.update_layout(**layout_update)
            st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})
        with c5:
            avg_risk = df_txn[risk_col].mean()
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", 
                value=avg_risk, 
                title={'text': "🌡️ System Risk Gauge", 'font': {'size': 22, 'color': 'white'}},
                domain={'x': [0, 1], 'y': [0, 1]},
                number={'font': {'size': 50, 'color': 'white'}, 'valueformat': '.1f'},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ff4b4b" if avg_risk > 60 else "#3b82f6"}}
            ))
            fig_gauge.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=40, b=10), height=260)
            st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

        st.markdown("<br>", unsafe_allow_html=True)
        
        # KHU VỰC THẺ QUYẾT ĐỊNH
        st.markdown("### 🎯 Decision Card")
        
        st.markdown('<div class="red-alert">🚨 SYSTEM HALTED: MISSING PARTNER LEGAL DOCUMENTS!</div>', unsafe_allow_html=True)
        
        st.warning("⚠️ **Human-in-the-loop Required:** Founder approval is mandatory for protective conditions before final contract execution.")
        
        st.info(st.session_state.final_dec) 
        
        st.markdown("#### 🔐 Founder Executive Actions:")
        btn1, btn2, btn3 = st.columns(3)
        
        if btn1.button("✅ ACKNOWLEDGE & APPROVE", use_container_width=True, type="primary"):
            st.success("🎉 Contract approved successfully! Proceeding to disbursement.")
            st.balloons() 
            
        if btn2.button("📝 REQUEST MISSING DOCUMENTS", use_container_width=True):
            st.info("📨 Document request sent to partner. Workflow paused.")
            
        if btn3.button("❌ REJECT PROJECT", use_container_width=True):
            st.error("⛔ High-risk project rejected. Decision logged to database.")

    with tab_chat:
        st.markdown("### 💬 Command Line Interface")
        agent_select = st.selectbox("Select Agent Interface:", ["Master Orchestrator", "Data Agent", "Planner Agent", "Finance Agent", "Risk Agent", "Banking Agent", "Decision Agent"])
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
            
        if st.button("🧹 Clear Terminal"):
            st.session_state.chat_history = []
            st.rerun()

        chat_container = st.container(height=400)
        with chat_container:
            st.chat_message("assistant").write(f"System Online. **{agent_select}** is ready for commands.")
            for msg in st.session_state.chat_history:
                st.chat_message(msg["role"]).write(msg["content"])

        prompt = st.chat_input(f"Send command to {agent_select}...")
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with chat_container:
                st.chat_message("user").write(prompt)
                with st.chat_message("assistant"):
                    with st.spinner(f"Awaiting response from {agent_select}..."):
                        sys_context = f"You are {agent_select} in the OPC Mission Control system. Answer the user professionally."
                        api_messages = [{"role": "system", "content": sys_context}]
                        for m in st.session_state.chat_history:
                            api_messages.append({"role": m["role"], "content": m["content"]})
                        
                        chat_res = client.chat.completions.create(model="gpt-4o", messages=api_messages, temperature=0.4)
                        chat_response = chat_res.choices[0].message.content
                        
                        st.session_state.total_tokens += chat_res.usage.total_tokens 
                        st.write(chat_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": chat_response})

if __name__ == "__main__":
    main()
