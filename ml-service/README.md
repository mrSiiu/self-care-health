# ML service (Python FastAPI)

Chưa khởi tạo mã nguồn. Hợp đồng API đã chốt ở [docs/03-thiet-ke.md](../docs/03-thiet-ke.md), mục 2.

- `POST /predict`: nhận `{evidences, age, sex}` → trả xác suất 49 bệnh DDXPlus
- `GET /health`, `GET /model-info`
- Mục tiêu: top-1 ≥ 90%, top-3 ≥ 97%, recall nhóm cần đi khám ≥ 98%
