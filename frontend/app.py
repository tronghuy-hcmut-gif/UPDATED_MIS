import os
import sys
import json
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    </style>
""", unsafe_allow_html=True)

# ĐỊA CHỈ BACKEND TRÊN RENDER
BACKEND_URL = "https://backend-qm8g.onrender.com"

# LẤY API KEY CHUẨN TRÊN RENDER
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except:
        pass

if not api_key:
    st.error("🚨 Không tìm thấy API Key! Hãy kiểm tra lại biến môi trường OPENAI_API_KEY trên Render.")
    st.stop()

client = OpenAI(api_key=api_key)

# CÁC HÀM AGENT
def agent_planner(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", response_format={ "type": "json_object" }, messages=[{"role": "system", "content": "Trả về JSON: { 'task_breakdown': '...', 'approval_gates': '...', 'workflow_plan': '...' } Tiếng Việt."}, {"role": "user", "content": data_bundle.get('contracts', '')}], temperature=0.1)
    parsed = json.loads(response.choices[0].message.content)
    return f"**Mục tiêu:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"

def agent_finance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tóm tắt ngắn 2 đoạn: Phân tích hụt vốn & Đề xuất giải pháp. Tiếng Việt."}, {"role": "user", "content": data_bundle.get('cashflow', '')}], temperature=0.1).choices[0].message.content

def agent_risk_compliance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Phân tích rủi ro ngắn gọn. Báo cáo giao dịch >= 85 điểm. Tiếng Việt."}, {"role": "user", "content": f"Data: {data_bundle.get('txn', '')}"}], temperature=0.1).choices[0].message.content

def agent_banking_integration(data_bundle):
    system_prompt = """
    Bạn là Giám đốc Quan hệ Khách hàng Doanh nghiệp (Corporate Banking Expert).
    Phân tích danh sách sản phẩm ngân hàng (data) và đề xuất đối tác tài trợ vốn tối ưu nhất.
    Trình bày Markdown. Ngôn từ chuyên nghiệp, sắc bén.
    """
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Dữ liệu ngân hàng: {data_bundle.get('bank_prod', '')}"}], temperature=0.3)
    return response.choices[0].message.content

def agent_decision(full_packet):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Đóng vai Tổng Giám Đốc. Phán quyết DUYỆT hoặc TỪ CHỐI. Trình bày max 4 câu sắc bén. Kèm Confidence Score %."}, {"role": "user", "content": full_packet}], temperature=0.1).choices[0].message.content

def main():
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False

    # GIAO DIỆN CHỜ (LANDING PAGE)
    if not st.session_state.data_loaded:
        st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
        col_L, col_C, col_R = st.columns([1, 2, 1])
        with col_C:
            st.markdown("<h1 style='text-align: center; color: white; text-shadow: 0 0 30px rgba(59,130,246,0.8);'>⚡ OPC COMMAND CENTER</h1>", unsafe_allow_html=True)
            st.markdown("<p style='text-align: center; color: #94a3b8; margin-bottom: 30px;'>Multi-Agent System Dashboard</p>", unsafe_allow_html=True)
            
            uploaded_file = st.file_uploader("", type=["xlsx"])
            if uploaded_file is not None:
                with st.spinner("Đang truyền dữ liệu lên Backend Server..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                    try:
                        # GỌI LÊN RENDER THAY VÌ LOCALHOST
                        res = requests.post(f"{BACKEND_URL}/upload", files=files)
                        if res.status_code == 200 and res.json().get("status") == "success":
                            
                            st.session_state.raw_data = requests.get(f"{BACKEND_URL}/api/data/raw").json()
                            dashboard_data = requests.get(f"{BACKEND_URL}/api/data/dashboard").json()
                            
                            st.session_state.df_cf = pd.DataFrame(dashboard_data['cashflow'])
                            st.session_state.df_txn = pd.DataFrame(dashboard_data['txn'])
                            
                            st.session_state.data_loaded = True
                            st.rerun() 
                        else:
                            st.error("Lỗi xử lý từ Backend!")
                    except requests.exceptions.ConnectionError:
                        st.error("🚨 Không thể kết nối tới Backend trên Render!")
        st.stop()

    # DASHBOARD
    raw_data = st.session_state.raw_data
    df_cf = st.session_state.df_cf
    df_txn = st.session_state.df_txn

    head_col1, head_col2 = st.columns([5, 1])
    with head_col1:
        st.markdown("## ⚡ OPC Multi-Agent Command Center")
    with head_col2:
        if st.button("🔄 Đóng Dashboard", use_container_width=True):
            st.session_state.clear() 
            st.rerun()

    if "ai_completed" not in st.session_state:
        with st.spinner("Đang nạp Data từ Backend và kích hoạt Đa Tác Nhân..."):
            st.session_state.p_rep = agent_planner(raw_data)
            st.session_state.f_rep = agent_finance(raw_data)
            st.session_state.r_rep = agent_risk_compliance(raw_data)
            st.session_state.b_rep = agent_banking_integration(raw_data)
            st.session_state.final_dec = agent_decision(f"{st.session_state.p_rep}\n\n[TÀI CHÍNH]\n{st.session_state.f_rep}\n\n[RỦI RO]\n{st.session_state.r_rep}")
            st.session_state.ai_completed = True

    tab_overview, tab_agents, tab_analysis, tab_dashboard, tab_chat = st.tabs([
        "🌐 Overview", "🤖 Agents Fleet", "🧠 Agent Analysis", "📊 Power Dashboard", "💬 Office & Chat"
    ])

    with tab_overview:
        st.markdown("### 📡 Trung tâm Điều hành AI (System Overview)")
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("LLM Engine", "gpt-4o", "Core API Online")
        m2.metric("Lực lượng Agent", "6 Chuyên gia", "Đang trực chiến")
        m3.metric("Tiến trình Task", "85% Hoàn thành", "Tốc độ xử lý +12%")
        m4.metric("Tài nguyên Token", "1,245,000", "Trong mức an toàn")
        
        st.divider()
        col_act, col_arch = st.columns([1, 1])
        with col_act:
            st.markdown("**🔄 Chuỗi nhiệm vụ thời gian thực (Recent Activities)**")
            st.progress(100, text="Data Agent: Đã nhận dữ liệu từ Backend Server (100%)")
            st.progress(100, text="Planner Agent: Đã khởi tạo cấu trúc Workflow (100%)")
            st.progress(80, text="Risk Agent: Đang quét dị thường giao dịch (80%)")
            st.progress(45, text="Finance Agent: Đang dự phóng hụt vốn dòng tiền (45%)")
            
        with col_arch:
            st.markdown("**🧠 Kiến trúc Suy luận (Reasoning Framework)**")
            st.info("""
            **Luồng xử lý dữ liệu chuẩn:**
            1. **Giao diện (Frontend):** Nhận file Excel và gửi lên Backend Cloud.
            2. **Kho Dữ liệu (Backend):** Bóc tách và giữ file trong RAM.
            3. **Tầng suy luận (Agentic Layer):** Frontend gọi API lấy Data thô từ Backend rồi ném cho 6 Agent xử lý.
            4. **Kết xuất (Output):** Khuyến nghị quyết định, tính toán độ tin cậy.
            """)

    with tab_agents:
        st.markdown("### 🤖 Đội hình Đặc nhiệm (6 Agents Fleet)")
        a1, a2, a3 = st.columns(3)
        with a1: st.success("**🎯 Planner Agent**\n\n- Đã xử lý: 420 tasks\n- Đóng góp: 25%")
        with a2: st.warning("**🛡️ Risk Agent**\n\n- Đã xử lý: 315 tasks\n- Đóng góp: 30%")
        with a3: st.info("**📊 Finance Agent**\n\n- Đã xử lý: 150 tasks\n- Đóng góp: 15%")
        
        st.markdown("<br>", unsafe_allow_html=True)
        z = [[1, 20, 30, 50, 1], [20, 1, 60, 80, 30], [30, 60, 1, -10, 20]]
        fig_heat = go.Figure(data=go.Heatmap(z=z, x=['T2', 'T3', 'T4', 'T5', 'T6'], y=['Sáng', 'Chiều', 'Tối'], colorscale='Blues')) 
        fig_heat.update_layout(title="💧 Heatmap Tần suất Hoạt động (Workload Distribution)", height=280, margin=dict(t=40, b=20, l=40, r=20), template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_heat, use_container_width=True)

    with tab_analysis:
        st.markdown("### 🧠 Phân tích Logic Đa Tác Nhân (Agent Reasoning)")
        st.success("**🎯 Planner Agent:** Khởi tạo cấu trúc phân rã công việc và ma trận phê duyệt.")
        with st.expander("📄 Xem chi tiết bản kế hoạch (Workflow Plan)"): st.markdown(st.session_state.p_rep)
            
        st.info("**📊 Finance Agent:** Đánh giá tình trạng thâm hụt dòng tiền dựa trên Cashflow.")
        with st.expander("📄 Xem chi tiết báo cáo tài chính (Financial Analysis)"): st.markdown(st.session_state.f_rep)
            
        st.warning("**🛡️ Risk Agent:** Quét toàn bộ giao dịch, định danh các điểm nghẽn rủi ro.")
        with st.expander("📄 Xem chi tiết rà soát tuân thủ (Risk & Compliance)"): st.markdown(st.session_state.r_rep)
            
        st.success("**🏦 Banking Agent:** Đối chiếu sản phẩm ngân hàng, đề xuất giải pháp tài trợ vốn.")
        with st.expander("📄 Xem chi tiết khuyến nghị API (Banking Integration)"): st.markdown(st.session_state.b_rep)

    with tab_dashboard:
        layout_update = dict(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=30, b=10), height=260)
        
        cash_col = df_cf.columns[-2]
        df_cf[cash_col] = pd.to_numeric(df_cf[cash_col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        risk_col = df_txn.columns[-1]
        df_txn[risk_col] = pd.to_numeric(df_txn[risk_col], errors='coerce').fillna(0)
        df_txn['Nhãn'] = df_txn[risk_col].apply(lambda x: 'Nguy hiểm' if x >= 85 else 'An toàn')
        df_txn['BubbleSize'] = df_txn[risk_col].apply(lambda x: max(x, 1))

        c1, c2, c3 = st.columns(3)
        with c1:
            fig_cf_line = px.line(df_cf, x=df_cf.columns[0], y=cash_col, title="📉 Xu hướng Dòng tiền", markers=True, color_discrete_sequence=['#3b82f6'])
            fig_cf_line.update_layout(**layout_update)
            st.plotly_chart(fig_cf_line, use_container_width=True, config={'displayModeBar': False})
        with c2:
            risk_counts = df_txn['Nhãn'].value_counts().reset_index()
            fig_pie = px.pie(risk_counts, values='count', names='Nhãn', title="🚨 Phân bổ Rủi ro", hole=0.6, color='Nhãn', color_discrete_map={'Nguy hiểm': '#ff4b4b', 'An toàn': '#3b82f6'})
            fig_pie.update_layout(**layout_update, showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        with c3:
            df_risk_top = df_txn.sort_values(by=risk_col, ascending=True).tail(5) 
            fig_bar = px.bar(df_risk_top, x=risk_col, y=df_txn.columns[0], orientation='h', title="🛡️ Top 5 Giao dịch Rủi ro", color=risk_col, color_continuous_scale='Blues')
            fig_bar.update_layout(**layout_update, showlegend=False)
            st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

        st.markdown("<br>", unsafe_allow_html=True)
        c4, c5 = st.columns([2, 1])
        with c4:
            fig_scatter = px.scatter(df_txn, x=df_txn.columns[0], y=risk_col, color='Nhãn', size='BubbleSize', title="📍 Phân tán Rủi ro (Anomaly Detection)", color_discrete_map={'Nguy hiểm': '#ff4b4b', 'An toàn': '#3b82f6'})
            fig_scatter.update_layout(**layout_update)
            st.plotly_chart(fig_scatter, use_container_width=True, config={'displayModeBar': False})
        with c5:
            avg_risk = df_txn[risk_col].mean()
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number", 
                value=avg_risk, 
                title={'text': "🌡️ Áp lực Rủi ro", 'font': {'size': 22}},
                domain={'x': [0, 1], 'y': [0, 1]},
                number={'font': {'size': 50}, 'valueformat': '.1f'},
                gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ff4b4b" if avg_risk > 60 else "#3b82f6"}}
            ))
            fig_gauge.update_layout(template="plotly_dark", plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", margin=dict(l=20, r=20, t=40, b=10), height=260)
            st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})

        st.markdown("### 🎯 Thẻ Quyết định (Decision Card)")
        st.error(st.session_state.final_dec)
        btn1, btn2 = st.columns(2)
        btn1.button("✅ DUYỆT (Approve)", use_container_width=True, type="primary")
        btn2.button("❌ TỪ CHỐI (Reject)", use_container_width=True)

    with tab_chat:
        st.markdown("### 💬 Agent Command Line")
        agent_select = st.selectbox("Chọn Agent để tương tác:", ["Master Orchestrator", "Planner Agent", "Finance Agent", "Risk Agent", "Banking Agent", "Document Agent", "Decision Agent"])
        
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []
            
        if st.button("🧹 Xóa hội thoại"):
            st.session_state.chat_history = []
            st.rerun()

        chat_container = st.container(height=400)
        with chat_container:
            st.chat_message("assistant").write(f"Xin chào! Tôi là **{agent_select}**. Dữ liệu hệ thống đã nạp từ Backend. Tôi có thể giúp gì cho bạn?")
            for msg in st.session_state.chat_history:
                st.chat_message(msg["role"]).write(msg["content"])

        prompt = st.chat_input(f"Giao task cho {agent_select}...")
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with chat_container:
                st.chat_message("user").write(prompt)
                with st.chat_message("assistant"):
                    with st.spinner(f"Đang gọi {agent_select}..."):
                        sys_context = f"Bạn là {agent_select} trong hệ thống. Hãy trả lời câu hỏi của người dùng chuyên nghiệp."
                        api_messages = [{"role": "system", "content": sys_context}]
                        for m in st.session_state.chat_history:
                            api_messages.append({"role": m["role"], "content": m["content"]})
                        
                        chat_response = client.chat.completions.create(model="gpt-4o", messages=api_messages, temperature=0.4).choices[0].message.content
                        st.write(chat_response)
                        st.session_state.chat_history.append({"role": "assistant", "content": chat_response})

if __name__ == "__main__":
    main()
