# ML service (Python FastAPI) – Giai đoạn 4

Mô hình dự đoán bệnh từ triệu chứng, train trên **DDXPlus** (49 bệnh, ~1,3 triệu ca), và service FastAPI
mà backend gọi qua `HttpMlAdapter`. Hợp đồng API: [docs/03-thiet-ke.md](../docs/03-thiet-ke.md), mục 2.
Phương pháp và cách đánh giá: [docs/04-hoc-may.md](../docs/04-hoc-may.md).

```
ml-service/
├── config/pham_vi.json     8 bệnh trong phạm vi, 7 bệnh luật, cách chọn bệnh rất nặng, ngưỡng, mục tiêu
├── ddx/                    đọc dữ liệu, mã hóa đặc trưng, mô hình, độ đo
├── scripts/
│   ├── kham_pha.py         B1: đếm ca 49 bệnh, severity, bảng evidence để dịch (đầu vào V3)
│   ├── train.py            B2: train nb / logreg / mlp, chọn mô hình, hiệu chỉnh xác suất
│   ├── evaluate.py         B3: đánh giá trên tập test, quét ngưỡng
│   ├── sinh_sql_benh.py    B4: sinh backend/.../V2__benh_ddxplus.sql
│   └── tao_du_lieu_gia.py  dữ liệu GIẢ cùng định dạng, chỉ để chạy thử code
├── app/                    FastAPI: /predict, /health, /model-info
├── tests/                  pytest (tự sinh dữ liệu giả, không cần DDXPlus)
├── models/                 model.joblib + model_info.json (không đưa lên git)
└── reports/                kết quả sinh ra, đưa vào quyển báo cáo
```

Mặc định các script đọc dữ liệu ở `data/raw/` (gốc repo, xem [data/README.md](../data/README.md)).
Dữ liệu ở chỗ khác thì thêm `--du-lieu <thư mục>`. Script tự tìm file kể cả khi file nằm trong thư mục con,
không có đuôi, hoặc vẫn là `.zip`.

## 1. Cài đặt và kiểm tra (Windows, PowerShell)
```powershell
cd ml-service
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -q          # 12 test
```

## 2. Train trên Kaggle
Kaggle có sẵn numpy, pandas, scikit-learn; train không cần FastAPI.

```python
# Ô 1 – lấy code (bật Internet trong Settings của notebook)
!git clone https://github.com/mrSiiu/self-care-health.git
%cd self-care-health/ml-service
import sklearn; print("scikit-learn", sklearn.__version__)   # ghi lại số này

# Ô 2 – đường dẫn dataset DDXPlus đã Add Input (xem ở khung Input bên phải)
DATA = "/kaggle/input/<ten-dataset-ddxplus>"

# Ô 3 – chạy pipeline
!python scripts/kham_pha.py      --du-lieu {DATA}
!python scripts/train.py         --du-lieu {DATA}
!python scripts/evaluate.py      --du-lieu {DATA}
!python scripts/sinh_sql_benh.py --du-lieu {DATA} --ra reports/V2__benh_ddxplus.sql

# Ô 4 – nén kết quả để tải về (Output → /kaggle/working)
!zip -r /kaggle/working/ket_qua_ml.zip models reports
```

Tải `ket_qua_ml.zip` về rồi giải nén vào `ml-service/`. `models/` giữ trên máy, không commit.
Thư mục `reports/` (các file `.md`, `.csv`) và `V2__benh_ddxplus.sql` thì commit.
Riêng V2, chép vào `backend/src/main/resources/db/migration/`.

> **Phiên bản scikit-learn phải trùng.** `model.joblib` là pickle, nên phải tải lại bằng đúng bản scikit-learn
> đã train trên Kaggle. Sửa dòng `scikit-learn` trong `requirements.txt` thành `scikit-learn==<số ở Ô 1>`
> rồi chạy `pip install -r requirements.txt` lại.

Thời gian ước lượng với đủ 1,0 triệu ca + 50% tăng cường: `nb` dưới 1 phút, `logreg` 10–30 phút, `mlp` 20–60 phút.
Cần chạy nhanh thì thêm `--toi-da-train 300000` hoặc `--mo-hinh nb,logreg`.
Tập test chỉ dùng **một lần** ở bước cuối. Chọn mô hình và nhiệt độ đều làm trên validate.

## 3. Chạy service
```powershell
uvicorn app.main:app --port 8000      # thử tại http://localhost:8000/docs
```
```json
POST /predict
{"evidences": ["E_91", "E_53", "E_55_@_V_89"], "age": 27, "sex": "F"}
→ {"model_version": "ddx-2026.11.19", "probabilities": [{"code": "URTI", "p": 0.6123}, ...], "ignored": []}
```
Chưa có mô hình thật mà cần thử ghép với backend: chạy `python scripts/tao_du_lieu_gia.py --ra data_gia`
rồi `python scripts/train.py --du-lieu data_gia` để có mô hình nháp. Không commit mô hình nháp, không dùng số đo của nó.

## 4. Sau khi dịch xong evidence (V3)
Chọn các evidence giao diện thật sự hỏi (cột `hien_thi_tren_app` trong `reports/evidences.csv`).
Ghi mã của chúng vào `config/evidence_giao_dien.txt`, mỗi dòng 1 mã `E_xx`, rồi train lại:
```powershell
python scripts/train.py    --danh-sach-evidence config/evidence_giao_dien.txt
python scripts/evaluate.py
```
