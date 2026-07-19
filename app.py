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

# Địa chỉ Backend trên Render của ông
BACKEND_URL = "https://backend-qm8g.onrender.com"

st.markdown("""
    <style>
        .stApp {
            background: radial-gradient(circle at 20% 30%, rgba(59, 130, 246, 0.15), transparent 40%),
                        radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.15), transparent 40%),
                        radial-gradient(circle at 50% 50%, rgba(255, 75, 75, 0.05), transparent 50%),
                        #080c16 !important;
            background-attachment: fixed;
        }
    </style>
""", unsafe_allow_html=True)

try:
    client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
except Exception as e:
    # Nếu dùng Render, Key nằm trong Environment Variable, 
    # nếu không thấy trong secrets thì lấy từ os.environ
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        st.error("🚨 Không tìm thấy API Key!")
        st.stop()
    client = OpenAI(api_key=api_key)

# ... (các hàm agent_planner, agent_finance, ... giữ nguyên) ...
def agent_planner(data_bundle):
    response = client.chat.completions.create(model="gpt-4o", response_format={ "type": "json_object" }, messages=[{"role": "system", "content": "Trả về JSON: { 'task_breakdown': '...', 'approval_gates': '...', 'workflow_plan': '...' } Tiếng Việt."}, {"role": "user", "content": data_bundle.get('contracts', '')}], temperature=0.1)
    parsed = json.loads(response.choices[0].message.content)
    return f"**Mục tiêu:** {parsed.get('task_breakdown', '')}\n\n**Workflow:** {parsed.get('workflow_plan', '')}"

def agent_finance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Tóm tắt ngắn 2 đoạn: Phân tích hụt vốn & Đề xuất giải pháp. Tiếng Việt."}, {"role": "user", "content": data_bundle.get('cashflow', '')}], temperature=0.1).choices[0].message.content

def agent_risk_compliance(data_bundle):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Phân tích rủi ro ngắn gọn. Báo cáo giao dịch >= 85 điểm. Tiếng Việt."}, {"role": "user", "content": f"Data: {data_bundle.get('txn', '')}"}], temperature=0.1).choices[0].message.content

def agent_banking_integration(data_bundle):
    system_prompt = "Bạn là Giám đốc Quan hệ Khách hàng Doanh nghiệp. Phân tích danh sách sản phẩm ngân hàng và đề xuất đối tác tài trợ vốn tối ưu nhất."
    response = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": f"Dữ liệu ngân hàng: {data_bundle.get('bank_prod', '')}"}], temperature=0.3)
    return response.choices[0].message.content

def agent_decision(full_packet):
    return client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": "Đóng vai Tổng Giám Đốc. Phán quyết DUYỆT hoặc TỪ CHỐI. Trình bày max 4 câu sắc bén."}, {"role": "user", "content": full_packet}], temperature=0.1).choices[0].message.content

def main():
    if "data_loaded" not in st.session_state:
        st.session_state.data_loaded = False

    if not st.session_state.data_loaded:
        st.markdown("<br><br><br><br><br>", unsafe_allow_html=True)
        col_L, col_C, col_R = st.columns([1, 2, 1])
        with col_C:
            st.markdown("<h1 style='text-align: center; color: white;'>⚡ OPC COMMAND CENTER</h1>", unsafe_allow_html=True)
            uploaded_file = st.file_uploader("", type=["xlsx"])
            if uploaded_file is not None:
                with st.spinner("Đang truyền dữ liệu lên Backend Server..."):
                    files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                    try:
                        # Gửi lên Backend Cloud
                        res = requests.post(f"{BACKEND_URL}/upload", files=files)
                        if res.status_code == 200 and res.json().get("status") == "success":
                            # Lấy data về
                            st.session_state.raw_data = requests.get(f"{BACKEND_URL}/api/data/raw").json()
                            dashboard_data = requests.get(f"{BACKEND_URL}/api/data/dashboard").json()
                            
                            st.session_state.df_cf = pd.DataFrame(dashboard_data['cashflow'])
                            st.session_state.df_txn = pd.DataFrame(dashboard_data['txn'])
                            
                            st.session_state.data_loaded = True
                            st.rerun() 
                        else:
                            st.error(f"Lỗi Backend: {res.text}")
                    except Exception as e:
                        st.error(f"🚨 Lỗi kết nối Backend: {e}")
        st.stop()

    # ... (phần Dashboard và các tab giữ nguyên không đổi) ...
    # Để tiết kiệm dung lượng, đoạn code dashboard/tab ông giữ nguyên như file cũ nhé!
    # Tui chỉ sửa lại mấy chỗ request tới BACKEND_URL thôi.

if __name__ == "__main__":
    main()
