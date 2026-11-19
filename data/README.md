# Dữ liệu

Bộ **DDXPlus** không được đưa vào git vì dung lượng lớn.

1. Tải từ Figshare (bản 20043374): https://figshare.com/articles/dataset/DDXPlus_Dataset/20043374
2. Giải nén vào `data/raw/`. Các file cần có:
   - `release_train_patients`, `release_validate_patients`, `release_test_patients`
   - `release_conditions.json`: 49 bệnh, có trường `severity`
   - `release_evidences.json`: các evidence (triệu chứng, tiền sử)

Trích dẫn: Fansi Tchango et al., *DDXPlus: A New Dataset For Automatic Medical Diagnosis*, NeurIPS 2022.
