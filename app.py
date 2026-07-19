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
# CẤU HÌNH GIAO DIỆN
# ==========================================
st.set_page_config(page_title="OPC Mission Control", page_icon="⚡", layout="wide")

# Địa chỉ Backend trên Render (Đã cập nhật)
BACKEND_URL = "https://backend-qm8g.onrender.com"

st.markdown("""
    <style>
        .stApp { background: #080c16 !important; }
        .stTabs [data-baseweb="tab"] { color: #94a3b8; }
        .stTabs [aria-selected="true"] { color: white !important; }
    </style>
""", unsafe_allow_html=True)

# Lấy API Key từ Environment Variable (phù hợp cho cả local và Render)
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    st.error("🚨 Không tìm thấy OPENAI_API_KEY trong hệ thống!")
    st.stop()
client = OpenAI(api_key=api_key)

# ==========================================
# CÁC HÀM AGENT
# ==========================================
def agent_planner(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", response_format={ "type": "json_object" }, messages=[{"role": "system", "content": "Trả về JSON: { 'task_breakdown': '...', 'approval_gates': '...', 'workflow_plan': '...' } Tiếng Việt."}, {"role": "user", "content": data_bundle.get('contracts', '')}], temperature=0.1)
    parsed = json.loads(response.choices[0].message.content)
    return f"**Mục tiêu:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"

def agent_finance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tóm tắt ngắn 2 đoạn: Phân tích hụt vốn & Đề xuất giải pháp. Tiếng Việt."}, {"role": "user", "content": data_bundle.get('cashflow', '')}], temperature=0.1).choices[0].message.content

def agent_risk_compliance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Phân tích rủi ro ngắn gọn. Báo cáo giao dịch >= 85 điểm. Tiếng Việt."}, {"role": "user", "content": f"Data: {data_bundle.get('txn', '')}"}], temperature=0.1).choices[0].message.content

def agent_banking_integration(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Giám đốc ngân hàng phân tích sản phẩm (data) và đề xuất tài trợ."}, {"role": "user", "content": f"Dữ liệu: {data_bundle.get('bank_prod', '')}"}], temperature=0.3)
    return response.choices[0].message.content

def agent_decision(full_packet):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tổng Giám Đốc phán quyết DUYỆT hoặc TỪ CHỐI. Max 4 câu."}, {"role": "user", "content": full_packet}], temperature=0.1).choices[0].message.content

# ==========================================
# HÀM CHÍNH
# ==========================================
def main():
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False

    if not st.session_state.data_loaded:
        st.markdown("<h1 style='text-align: center; color: white;'>⚡ OPC COMMAND CENTER</h1>", unsafe_allow_html=True)
        uploaded_file = st.file_uploader("Upload File Excel", type=["xlsx"])
        if uploaded_file is not None:
            with st.spinner("Đang truyền dữ liệu lên Backend..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                try:
                    res = requests.post(f"{BACKEND_URL}/upload", files=files)
                    if res.status_code == 200:
                        st.session_state.raw_data = requests.get(f"{BACKEND_URL}/api/data/raw").json()
                        dash = requests.get(f"{BACKEND_URL}/api/data/dashboard").json()
                        st.session_state.df_cf = pd.DataFrame(dash['cashflow'])
                        st.session_state.df_txn = pd.DataFrame(dash['txn'])
                        st.session_state.data_loaded = True
                        st.rerun()
                    else:
                        st.error("Lỗi Backend!")
                except Exception as e:
                    st.error(f"Lỗi kết nối: {e}")
        st.stop()

    # DASHBOARD
    st.markdown("## ⚡ OPC Multi-Agent Command Center")
    if st.button("🔄 Đóng Dashboard"):
        st.session_state.clear()
        st.rerun()

    if "ai_completed" not in st.session_state:
        with st.spinner("Đang chạy AI Agents..."):
            st.session_state.p = agent_planner(st.session_state.raw_data)
            st.session_state.f = agent_finance(st.session_state.raw_data)
            st.session_state.r = agent_risk_compliance(st.session_state.raw_data)
            st.session_state.b = agent_banking_integration(st.session_state.raw_data)
            st.session_state.dec = agent_decision(f"{st.session_state.p}\n{st.session_state.f}\n{st.session_state.r}")
            st.session_state.ai_completed = True

    tab1, tab2 = st.tabs(["📊 Dashboard", "🧠 Agent Analysis"])
    with tab1:
        st.line_chart(st.session_state.df_cf)
    with tab2:
        st.write(st.session_state.dec)
        st.markdown("---")
        st.write(st.session_state.p)
        st.write(st.session_state.f)

if __name__ == "__main__":
    main()
