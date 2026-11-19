"""Sinh migration V2__benh_ddxplus.sql (49 bệnh DDXPlus + 7 bệnh luật).

  python scripts/sinh_sql_benh.py --du-lieu <thư mục DDXPlus> \
      --ra ../backend/src/main/resources/db/migration/V2__benh_ddxplus.sql

- 8 bệnh trong phạm vi: tên tiếng Việt lấy từ config/pham_vi.json.
- 41 bệnh còn lại: ten_vi tạm = tên tiếng Anh (dòng có chú thích -- TODO dịch).
  Các bệnh này không bao giờ hiển thị tên cho người dùng nếu rat_nang (BR19).
- rat_nang: 2 bậc severity nặng nhất, trừ bệnh trong phạm vi (CHECK của bảng).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddx.data import doc_cau_hinh, doc_json, giai_pham_vi, giai_rat_nang  # noqa: E402

GOC = Path(__file__).resolve().parents[1]


def q(s):
    return "NULL" if s is None else "'" + str(s).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--du-lieu", default=str(GOC.parent / "data/raw"), help="thư mục DDXPlus (mặc định: data/raw ở gốc repo)")
    ap.add_argument("--cau-hinh", default=str(GOC / "config/pham_vi.json"))
    ap.add_argument("--ra", default=str(GOC.parent / "backend/src/main/resources/db/migration/V2__benh_ddxplus.sql"))
    a = ap.parse_args()
    cond = doc_json(a.du_lieu, "release_conditions.json")
    ch = doc_cau_hinh(a.cau_hinh)
    pv = giai_pham_vi(cond, ch)
    rn, chieu = giai_rat_nang(cond, ch)
    rn -= set(pv)

    dong = ["-- V2__benh_ddxplus.sql — sinh tự động bởi ml-service/scripts/sinh_sql_benh.py",
            f"-- Nguồn: release_conditions.json ({len(cond)} bệnh). Thang severity: {chieu}.",
            "INSERT INTO benh (ma_ddxplus, ten_vi, ten_en, nhom, nguon, trong_pham_vi, muc_mac_dinh, severity_ddxplus, rat_nang) VALUES"]
    gia_tri = []
    for k in sorted(cond, key=lambda k: (k not in pv, k not in rn, k)):
        c = cond[k]
        ten_en = c.get("cond-name-eng") or k
        if k in pv:
            ten_vi, nhom, muc, ghi = pv[k]["ten_vi"], pv[k]["nhom"], 1, ""
        else:
            ten_vi, nhom, muc, ghi = ten_en, "KHAC", 3 if k in rn else 2, "  -- TODO dịch ten_vi"
        gia_tri.append(f" ({q(k)}, {q(ten_vi)}, {q(ten_en)}, {q(nhom)}, 'ML', {str(k in pv).lower()}, {muc}, "
                       f"{c.get('severity', 'NULL')}, {str(k in rn).lower()}){{SEP}}{ghi}")
    for i, g in enumerate(gia_tri):
        dong.append(g.replace("{SEP}", ";" if i == len(gia_tri) - 1 else ","))
    dong += ["", "-- 7 bệnh ngoài DDXPlus, suy luận bằng luật (luật nằm ở V4)",
             "INSERT INTO benh (ma_ddxplus, ten_vi, ten_en, nhom, nguon, trong_pham_vi, muc_mac_dinh, severity_ddxplus, rat_nang) VALUES"]
    luat = ch["benh_luat"]
    for i, b in enumerate(luat):
        dong.append(f" (NULL, {q(b['ten_vi'])}, NULL, {q(b['nhom'])}, 'LUAT', true, {b['muc_mac_dinh']}, NULL, false)"
                    + (";" if i == len(luat) - 1 else ","))
    Path(a.ra).parent.mkdir(parents=True, exist_ok=True)
    Path(a.ra).write_text("\n".join(dong) + "\n", encoding="utf-8")
    print(f"Đã ghi {a.ra}: {len(cond)} bệnh ML ({len(pv)} trong phạm vi, {len(rn)} rất nặng) + {len(luat)} bệnh luật")


if __name__ == "__main__":
    main()
