# GIAI ĐOẠN 4: HỌC MÁY – MÔ HÌNH SÀNG LỌC TRÊN DDXPLUS

**Đề tài:** Nền tảng hỗ trợ tự chăm sóc sức khỏe tại nhà cho người sống một mình: sàng lọc triệu chứng, hướng dẫn chăm sóc và cảnh báo người thân, tích hợp Học máy

**Đầu vào:** [Nghiệp vụ v1.1](01-phan-tich-nghiep-vu.md) (15 bệnh, ngưỡng, mục tiêu mô hình), [Thiết kế](03-thiet-ke.md) mục 2 (hợp đồng `/predict`) và mục 4.3 (chuỗi mức xử lý).
**Mã nguồn:** [`ml-service/`](../ml-service/). Cách chạy (máy cá nhân, Kaggle): [`ml-service/README.md`](../ml-service/README.md).

> Các bảng kết quả ở mục 6 để trống vì phải điền bằng số đo thật sau khi chạy pipeline trên DDXPlus. Code đã được chạy thử trên dữ liệu giả cùng định dạng; số đo trên dữ liệu giả không được đưa vào báo cáo.

---

## 1. Bài toán
| | |
|---|---|
| Loại bài toán | Phân loại đa lớp có xác suất (49 lớp) |
| Đầu vào | Danh sách mã evidence (`E_91`, `E_55_@_V_89`, …), tuổi, giới tính |
| Đầu ra | Xác suất của đủ 49 bệnh DDXPlus, sắp giảm dần |
| Dùng ở đâu | Backend dùng xác suất cho chuỗi mức xử lý: lưới an toàn (P bệnh rất nặng ≥ 0,10), ngoài phạm vi (tổng ≥ 0,15), độ tin cậy (top-1 ≥ 0,50) |

**Vì sao học đủ 49 bệnh mà không chỉ 8 bệnh?** Nếu chỉ học 8 bệnh nhẹ, mô hình luôn trả về một bệnh nhẹ, kể cả khi người dùng bị viêm phổi hay thuyên tắc phổi. Học đủ 49 bệnh thì xác suất dồn sang bệnh nặng khi triệu chứng giống bệnh nặng. Backend dựa vào đó để nâng mức xử lý.

## 2. Dữ liệu
- **DDXPlus** (Fansi Tchango và cộng sự, NeurIPS 2022; Figshare 20043374): khoảng 1,3 triệu ca bệnh nhân tổng hợp, sinh từ cơ sở tri thức y khoa do chuyên gia xây dựng. Có sẵn 3 tập train / validate / test.
- Mỗi ca có tuổi, giới tính, bệnh thật (`PATHOLOGY`), danh sách evidence, evidence ban đầu (lý do đi khám).
- Evidence có 3 kiểu: **B** (có/không), **C** (một giá trị, ví dụ mức đau 0–10), **M** (nhiều lựa chọn, ví dụ vị trí đau).
- Script `kham_pha.py` sinh: số ca từng bệnh ở 3 tập, thang severity, tỷ lệ 8 bệnh trong phạm vi, danh sách evidence kèm tần suất (`reports/evidences.csv` – đầu vào để dịch tiếng Việt cho V3).

**Hạn chế cần nêu trong báo cáo:** dữ liệu là tổng hợp và dựa trên dịch tễ học Canada, không phải ca bệnh thật của người Việt. Vì vậy hệ thống chỉ **sàng lọc**, không chẩn đoán. Kiểm thử bổ sung bằng 30 ca tiếng Việt tự soạn (mục 6.4).

## 3. Tiền xử lý và đặc trưng
| Bước | Cách làm | Lý do |
|---|---|---|
| Đọc evidence | Tách chuỗi `"['E_48', ...]"` bằng split, `sys.intern` từng mã | Nhanh hơn `ast.literal_eval` khoảng 7 lần (đo thử); tiết kiệm RAM khi có hàng triệu chuỗi trùng nhau |
| Mã hóa evidence | **Multi-hot**: mỗi token (`E_91`, `E_54_@_V_161`, `E_56_@_7`) là một cột 0/1 | Không cần biết trước kiểu từng câu hỏi; giữ đúng ý nghĩa DDXPlus; ma trận thưa nên nhẹ |
| Lọc token | Bỏ token xuất hiện < 5 lần trong train | Tránh nhiễu |
| Tuổi | One-hot 8 nhóm: <1, 1–4, 5–14, 15–29, 30–44, 45–59, 60–74, ≥75 | Quan hệ tuổi–bệnh không tuyến tính (ví dụ croup ở trẻ em, nhồi máu cơ tim ở người lớn tuổi) |
| Giới tính | One-hot M/F | |
| Token lạ khi dự đoán | Bỏ qua, trả trong trường `ignored` | Đúng thiết kế mục 2.2: không làm hỏng cả lần sàng lọc |
| Giới hạn evidence theo giao diện | Tùy chọn `--danh-sach-evidence` | Sau khi chốt V3, chỉ train trên những evidence app thực sự hỏi người dùng |

## 4. Tăng cường dữ liệu: mô phỏng người dùng khai thiếu
**Vấn đề.** DDXPlus sinh ca bằng một quy trình hỏi đáp đầy đủ, nên mỗi ca có hơn chục evidence (số chính xác ghi ở `reports/kham_pha.md`). Người dùng app chỉ chọn vài triệu chứng nổi bật trong danh sách tiếng Việt. Mô hình chỉ học trên ca đầy đủ sẽ quá tự tin khi gặp đầu vào thiếu.

**Cách làm.** Nhân bản ngẫu nhiên 50% số ca train. Mỗi bản sao giữ ngẫu nhiên 30–80% evidence, **luôn giữ evidence ban đầu** (lý do người dùng mở app) và ít nhất 1 evidence. Mô hình được train trên ca gốc cộng với các bản sao.

**Đánh giá ở 3 điều kiện:** đủ evidence, giữ 50%, giữ 30%. Điều kiện "giữ 50%" được dùng để chọn ngưỡng, vì nó gần với cách người dùng thật khai triệu chứng.

## 5. Mô hình và quy trình chọn
### 5.1 Ứng viên
| Mô hình | Cấu hình | Vai trò |
|---|---|---|
| Bernoulli Naive Bayes | α = 1 | Mốc cơ sở: train nhanh, dễ giải thích |
| Logistic Regression đa lớp (softmax) | solver saga, C = 1 | Tuyến tính, xác suất khá chuẩn, trọng số đọc được (triệu chứng nào đẩy bệnh nào) |
| MLP | 1 lớp ẩn 256 nơ-ron, Adam, early stopping | Học được tổ hợp triệu chứng (ví dụ "sốt + ho + đau ngực") |

Không dùng mô hình lớn hơn (Transformer, mô hình hỏi đáp tương tác như AARLC) vì: (1) với DDXPlus, mô hình đơn giản đã đạt top-1 cao; (2) service phải trả lời trong 2 giây (NFR03) trên máy demo; (3) phần cần chứng minh trong đồ án là **an toàn** của cả hệ thống, không phải độ chính xác cao nhất.

### 5.2 Chọn mô hình
1. Train mỗi ứng viên trên train + tăng cường.
2. Chấm trên **validate** ở 2 điều kiện (đủ, giữ 50%).
3. Chọn mô hình có **top-1 trung bình hai điều kiện** cao nhất.
4. Tập **test chỉ dùng một lần** ở bước cuối (`evaluate.py`), không dùng để chọn hay chỉnh.

### 5.3 Hiệu chỉnh xác suất (temperature scaling)
Ngưỡng nghiệp vụ được áp trực tiếp lên xác suất, nên xác suất phải "đúng nghĩa": các ca mô hình báo P ≈ 0,7 thì khoảng 70% số đó phải đúng. Sau khi chọn mô hình, tìm nhiệt độ T làm nhỏ log-loss trên validate, rồi áp `p ∝ p^(1/T)`. Cách này không đổi thứ hạng bệnh, nên top-k không đổi; chỉ làm xác suất bớt quá tự tin (T > 1) hoặc bớt rụt rè (T < 1). Độ đo kiểm tra: **ECE** (Expected Calibration Error, 15 khoảng).

## 6. Đánh giá
### 6.1 Độ đo
| Độ đo | Định nghĩa | Mục tiêu (nghiệp vụ v1.1) |
|---|---|---|
| Top-1, Top-3 | Bệnh thật nằm trong 1 / 3 bệnh xác suất cao nhất (49 lớp) | ≥ 90% / ≥ 97% |
| **Recall nhóm cần đi khám** | Trong các ca có bệnh **ngoài** 8 bệnh tự chăm sóc, tỷ lệ được xếp mức ≥ 2 | ≥ 98% |
| Bệnh rất nặng lên mức 3 | Trong các ca bệnh rất nặng, tỷ lệ được xếp mức 3 | Báo cáo |
| Báo động thừa | Trong các ca thuộc 8 bệnh nhẹ, tỷ lệ bị xếp mức ≥ 2 | Báo cáo (càng thấp càng tốt) |
| ECE | Sai lệch giữa độ tự tin và tỷ lệ đúng | Báo cáo |

**Cách tính recall nhóm cần đi khám.** `ddx/metrics.py` mô phỏng lại 3 mắt xích dùng xác suất ML trong `BoDanhGiaMucXuLy` (10 LuoiAnToan, 20 NgoaiPhamVi, 30 DoTinCayML + 99 DanhSachRong). Luật 7 bệnh, red flag và ngưỡng Phụ lục B không được mô phỏng. Các bước này chỉ nâng mức, nên hệ thống thật an toàn **hơn hoặc bằng** số đo này.

**Bệnh rất nặng** được chọn tự động: 2 bậc severity nặng nhất trong `release_conditions.json`, trừ 8 bệnh trong phạm vi. Script tự dò chiều của thang severity bằng các bệnh mốc (thuyên tắc phổi, sốc phản vệ so với URTI). Danh sách này được ghi vào cột `benh.rat_nang` của V2, và quản trị nội dung vẫn sửa được.

### 6.2 Kết quả trên tập test *(điền sau khi chạy `evaluate.py`)*
| Điều kiện | Top-1 | Top-3 | ECE | Recall cần khám | Bệnh rất nặng → mức 3 | Báo động thừa |
|---|---|---|---|---|---|---|
| Đủ evidence | | | | | | |
| Giữ 50% | | | | | | |
| Giữ 30% | | | | | | |

### 6.3 Chọn lại ngưỡng
`evaluate.py` quét ngưỡng top-1 (0,30–0,70) × ngưỡng rất nặng (0,05 / 0,10 / 0,20) ở điều kiện giữ 50%. **Quy tắc chọn:** trong các cặp ngưỡng có recall cần khám ≥ 98%, chọn cặp có báo động thừa thấp nhất. Giá trị chọn được ghi vào bảng `cau_hinh` (`sang_loc.nguong_top1`, `sang_loc.nguong_rat_nang`), không phải sửa code (NFR06).

### 6.4 Kiểm thử 30 ca tiếng Việt *(sau V3)*
Mỗi ca gồm mô tả tiếng Việt, các triệu chứng chọn trên giao diện, bệnh và mức xử lý mong đợi. Cách chạy: đi qua ánh xạ tiếng Việt → mã evidence của backend, rồi gọi `/predict`. Kết quả được ghi cùng bảng test case của Giai đoạn 6.

## 7. Triển khai mô hình
- File `models/model.joblib` gồm mô hình, bộ mã hóa (từ vựng token), nhiệt độ T, phiên bản và các độ đo. Kèm `model_info.json` để đọc nhanh.
- Phiên bản dạng `ddx-YYYY.MM.DD`; được lưu vào `lan_sang_loc.phien_ban_mo_hinh` mỗi lần sàng lọc.
- Service FastAPI: `POST /predict`, `GET /health` (healthcheck Docker), `GET /model-info`. Đầu vào được kiểm tra: tuổi 0–120, giới tính M/F, tối đa 300 evidence (sai → HTTP 422).
- Mô hình chỉ được tải từ file do chính pipeline sinh ra (joblib dùng pickle, không tải file từ nguồn ngoài).

## 8. Kiểm thử phần ML
`python -m pytest -q`: test tự sinh dữ liệu giả, train một mô hình nhỏ, rồi kiểm tra:
- tách chuỗi evidence; bỏ token lạ; danh sách evidence giao diện;
- bỏ bớt evidence luôn giữ evidence ban đầu; nhiệt độ giữ tổng xác suất bằng 1 và giữ thứ hạng;
- 5 ca của chuỗi mức xử lý, gồm ca Đ2: top-1 = 0,60 nhưng viêm phổi = 0,20 → mức 3;
- phản hồi `/predict` đúng hợp đồng: đủ lớp, sắp giảm dần, tổng ≈ 1, có `ignored`; HTTP 422 khi đầu vào sai.

## 9. Việc còn mở
- [ ] Chạy `kham_pha.py` trên DDXPlus thật, kiểm tra tên 8 bệnh khớp và danh sách bệnh rất nặng.
- [ ] Chạy `train.py` và `evaluate.py`, điền bảng 6.2, chọn ngưỡng theo 6.3.
- [ ] Chạy `sinh_sql_benh.py` → chép `V2__benh_ddxplus.sql` vào backend; dịch `ten_vi` cho 41 bệnh ngoài phạm vi.
- [ ] Dịch `reports/evidences.csv` → V3; chọn evidence hiển thị → train lại với `--danh-sach-evidence`.
- [ ] Soạn 30 ca tiếng Việt (6.4).
