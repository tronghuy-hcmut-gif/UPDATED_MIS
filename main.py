from fastapi import FastAPI, UploadFile, File
import pandas as pd
import io

app = FastAPI(title="OPC Data Server")

# Cục RAM tạm thời để lưu dữ liệu của các sheet
DATA_STORE = {}

@app.get("/")
def read_root():
    return {"status": "Backend Server is running ⚡"}

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """API nhận file Excel từ giao diện và bóc tách lưu vào RAM"""
    contents = await file.read()
    
    try:
        # Bóc tách từng sheet và lưu dưới dạng List of Dictionaries
        DATA_STORE['contracts'] = pd.read_excel(io.BytesIO(contents), sheet_name='04_CONTRACTS').to_dict(orient="records")
        DATA_STORE['cashflow'] = pd.read_excel(io.BytesIO(contents), sheet_name='09_CASHFLOW').to_dict(orient="records")
        DATA_STORE['txn'] = pd.read_excel(io.BytesIO(contents), sheet_name='08_BANK_TXN').to_dict(orient="records")
        DATA_STORE['rules'] = pd.read_excel(io.BytesIO(contents), sheet_name='13_RISK_RULES').to_dict(orient="records")
        DATA_STORE['bank_prod'] = pd.read_excel(io.BytesIO(contents), sheet_name='11_BANK_PRODUCTS').to_dict(orient="records")
        return {"status": "success", "message": "Đã hóa lỏng dữ liệu vào Backend thành công!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/data/raw")
def get_raw_data():
    """API cung cấp dữ liệu thô dạng chuỗi (String) cho các Agent AI"""
    if not DATA_STORE:
        return {"error": "Chưa có dữ liệu"}
    return {
        "contracts": str(DATA_STORE.get('contracts', '')),
        "cashflow": str(DATA_STORE.get('cashflow', '')),
        "txn": str(DATA_STORE.get('txn', '')),
        "rules": str(DATA_STORE.get('rules', '')),
        "bank_prod": str(DATA_STORE.get('bank_prod', ''))
    }

@app.get("/api/data/dashboard")
def get_dashboard_data():
    """API cung cấp dữ liệu dạng JSON cho biểu đồ ở Tab 4"""
    if not DATA_STORE:
        return {"error": "Chưa có dữ liệu"}
    return {
        "cashflow": DATA_STORE.get('cashflow', []),
        "txn": DATA_STORE.get('txn', [])
    }