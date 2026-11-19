# Self-Care Health

**Nền tảng hỗ trợ tự chăm sóc sức khỏe tại nhà cho người sống một mình: sàng lọc triệu chứng, hướng dẫn chăm sóc và cảnh báo người thân, tích hợp Học máy.**

> ⚠️ Hệ thống chỉ **hỗ trợ sàng lọc**. Hệ thống không chẩn đoán, không kê đơn, không đưa liều thuốc và không thay thế bác sĩ. Đây là đồ án học tập, chưa dùng cho người bệnh thật.

## Tính năng chính
- **Sàng lọc triệu chứng:** người dùng chọn triệu chứng tiếng Việt. Hệ thống kiểm tra dấu hiệu nguy hiểm trước, sau đó chạy song song mô hình ML (train trên DDXPlus, 49 bệnh) và bộ luật (7 bệnh). Kết quả gồm tối đa 3 khả năng bệnh và mức xử lý (tự chăm sóc / khám trong 24–48 giờ / khám ngay).
- **Hướng dẫn tự chăm sóc** cho 15 bệnh thường gặp, có ghi nguồn tham khảo.
- **Tủ thuốc:** cảnh báo trùng hoạt chất, cảnh báo NSAID khi nghi sốt xuất huyết.
- **Nhật ký và cảnh báo người thân:** nhắc ghi nhật ký lúc 8:00 và 20:00. Người dùng không phản hồi hoặc mức xử lý tăng thì hệ thống gửi email cho người thân.

## Kiến trúc
| Thành phần | Công nghệ | Thư mục |
|---|---|---|
| Backend | Spring Boot 3 (Java 21), modular monolith | [`backend/`](backend/) |
| Dịch vụ ML | Python FastAPI | [`ml-service/`](ml-service/) |
| Frontend | React + Vite | [`frontend/`](frontend/) |
| CSDL | PostgreSQL 16 + Flyway | [`backend/src/main/resources/db/migration/`](backend/src/main/resources/db/migration/) |
| Email (demo) | Mailpit | [`docker-compose.yml`](docker-compose.yml) |

## Tài liệu
| # | Tài liệu | Nội dung |
|---|---|---|
| 1 | [Phân tích nghiệp vụ](docs/01-phan-tich-nghiep-vu.md) | Bối cảnh, phạm vi, tác nhân, quy trình, quy tắc BR01–BR14, use case, NFR, 15 bệnh, ngưỡng |
| 2 | [Phân tích hệ thống + UML](docs/02-phan-tich-he-thong.md) | Use case phân rã, đặc tả, sơ đồ hoạt động, tuần tự, lớp, trạng thái; đề xuất Đ1–Đ6, BR15–BR20 |
| 3 | [Thiết kế](docs/03-thiet-ke.md) | Kiến trúc, ERD, SQL, design pattern, API, bảo mật, scheduler |
| 4 | [Học máy](docs/04-hoc-may.md) | Dữ liệu DDXPlus, đặc trưng, tăng cường dữ liệu, chọn mô hình, hiệu chỉnh xác suất, đánh giá an toàn. Code: [`ml-service/`](ml-service/) |

Các sơ đồ viết bằng PlantUML. Có thể xem bằng [planttext.com](https://www.planttext.com) hoặc extension PlantUML trên VS Code.

## Chạy thử (đang dựng dần)
Hiện mới chạy được phần hạ tầng: PostgreSQL và Mailpit.
```bash
cp .env.example .env
docker compose up -d
# Nạp schema (khi chưa có backend/Flyway):
docker compose exec -T postgres psql -U hmnc -d hmnc < backend/src/main/resources/db/migration/V1__khoi_tao_csdl.sql
# Xem email demo: http://localhost:8025
```


## Dữ liệu
Bộ dữ liệu **DDXPlus** (Fansi Tchango et al., NeurIPS 2022, Figshare 20043374) không được đưa vào repo. Xem hướng dẫn tải ở [`data/README.md`](data/README.md).
