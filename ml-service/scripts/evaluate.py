"""Bước 3 – Đánh giá mô hình đã lưu trên tập TEST (chỉ chạy 1 lần cho báo cáo).

  python scripts/evaluate.py --du-lieu <thư mục DDXPlus>

Đầu ra: reports/danh_gia.md, reports/danh_gia.json
  - Top-1/3/5, ECE ở 3 điều kiện: đủ evidence, giữ 50%, giữ 30%
  - Bảng 8 bệnh: precision, recall, top-3, nhầm lẫn nhiều nhất
  - Chỉ tiêu an toàn: recall cần khám, recall bệnh rất nặng lên mức 3
  - Quét ngưỡng top-1 và ngưỡng rất nặng để chọn giá trị cấu hình
"""
import argparse
import json
import sys
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddx.data import doc_cau_hinh, doc_tap  # noqa: E402
from ddx.features import bo_bot_evidence  # noqa: E402
from ddx.metrics import bao_cao, nham_lan_nhieu_nhat, theo_tung_benh  # noqa: E402
from ddx.model import GoiMoHinh  # noqa: E402

GOC = Path(__file__).resolve().parents[1]


def pt(x):
    return "–" if x is None else f"{x:.2%}"


def dat(x, muc_tieu):
    return "–" if x is None else ("✅" if x >= muc_tieu else "❌")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--du-lieu", default=str(GOC.parent / "data/raw"), help="thư mục DDXPlus (mặc định: data/raw ở gốc repo)")
    ap.add_argument("--mo-hinh", default=str(GOC / "models/model.joblib"))
    ap.add_argument("--cau-hinh", default=str(GOC / "config/pham_vi.json"))
    ap.add_argument("--bao-cao", default=str(GOC / "reports"), help="thư mục ghi danh_gia.md/json")
    ap.add_argument("--toi-da", type=int, default=None, help="giới hạn số ca test (mặc định: tất cả)")
    a = ap.parse_args()
    ch = doc_cau_hinh(a.cau_hinh)
    goi = GoiMoHinh.from_dict(joblib.load(a.mo_hinh))
    tt = goi.thong_tin
    lop, pham_vi, rat_nang, ng = goi.lop, set(tt["in_scope"]), set(tt["very_severe"]), ch["nguong"]
    ten_vi = tt.get("in_scope_vi", {})

    te = doc_tap(a.du_lieu, "test", a.toi_da)
    vi_tri = {c: i for i, c in enumerate(lop)}
    y = np.array([vi_tri.get(n, -1) for n in te.nhan]); giu = y >= 0
    if (~giu).any():
        print(f"Cảnh báo: bỏ {(~giu).sum()} ca test có bệnh mô hình chưa thấy khi train")
    rng = np.random.default_rng(7)
    dieu_kien = {"Đủ evidence": te.evidences,
                 "Giữ 50% evidence": bo_bot_evidence(te.evidences, te.evidence_ban_dau, 0.5, rng),
                 "Giữ 30% evidence": bo_bot_evidence(te.evidences, te.evidence_ban_dau, 0.3, rng)}
    P, BC = {}, {}
    for ten, evs in dieu_kien.items():
        P[ten] = goi.xac_suat([e for e, g in zip(evs, giu) if g], np.array(te.tuoi)[giu], np.array(te.gioi_tinh)[giu])
        BC[ten] = bao_cao(P[ten], y[giu], lop, pham_vi, rat_nang, ng)
        print(f"{ten}: top1={BC[ten]['top1']:.4f} top3={BC[ten]['top3']:.4f} recall_can_kham={BC[ten]['recall_can_kham']}")

    mt = ch["muc_tieu"]
    d = BC["Đủ evidence"]
    md = [f"# Đánh giá mô hình trên tập test DDXPlus", "",
          f"Mô hình `{goi.phien_ban}` ({tt['algorithm']}, T = {tt['temperature']:.3f}), train lúc {tt['trained_at']}. "
          f"Số ca test: {d['so_ca']:,}.", "",
          "## 1. So với mục tiêu (đủ evidence)", "",
          "| Chỉ tiêu | Mục tiêu | Đạt được | |", "|---|---|---|---|",
          f"| Top-1 (49 bệnh) | ≥ {mt['top1']:.0%} | {pt(d['top1'])} | {dat(d['top1'], mt['top1'])} |",
          f"| Top-3 (49 bệnh) | ≥ {mt['top3']:.0%} | {pt(d['top3'])} | {dat(d['top3'], mt['top3'])} |",
          f"| Recall nhóm cần đi khám | ≥ {mt['recall_can_kham']:.0%} | {pt(d['recall_can_kham'])} | "
          f"{dat(d['recall_can_kham'], mt['recall_can_kham'])} |", "",
          "> *Recall nhóm cần đi khám* = trong các ca có bệnh **ngoài** 8 bệnh tự chăm sóc, tỷ lệ được hệ thống "
          "xếp mức ≥ 2. Chỉ tính 3 mắt xích dùng xác suất ML (lưới an toàn, ngoài phạm vi, độ tin cậy); luật, red flag "
          "và ngưỡng Phụ lục B chỉ nâng mức thêm, nên hệ thống thật an toàn hơn hoặc bằng số này.", "",
          "## 2. Ảnh hưởng của việc khai thiếu triệu chứng", "",
          "| Điều kiện | Top-1 | Top-3 | Top-5 | ECE | Top-1 (8 bệnh) | Recall cần khám | Bệnh rất nặng lên mức 3 | "
          "Báo động thừa | Hiển thị đúng bệnh |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for ten, b in BC.items():
        md.append(f"| {ten} | {pt(b['top1'])} | {pt(b['top3'])} | {pt(b['top5'])} | {b['ece']:.4f} | {pt(b['top1_8_benh'])} | "
                  f"{pt(b['recall_can_kham'])} | {pt(b['recall_rat_nang_muc3'])} | {pt(b['bao_dong_thua'])} | "
                  f"{pt(b['hien_thi_dung'])} |")
    md += ["", "> *Báo động thừa* = ca thuộc 8 bệnh nhẹ nhưng bị xếp mức ≥ 2 (an toàn nhưng làm phiền). "
           "*Hiển thị đúng bệnh* = ca thuộc 8 bệnh được giữ ở mức 1 và top-1 đúng.", "",
           "## 3. Từng bệnh trong phạm vi (đủ evidence)", "",
           "| Bệnh | Số ca | Precision | Recall | Top-3 recall | Hay nhầm với |", "|---|---|---|---|---|---|"]
    nl = nham_lan_nhieu_nhat(P["Đủ evidence"], y[giu], lop, sorted(pham_vi))
    for r in theo_tung_benh(P["Đủ evidence"], y[giu], lop, sorted(pham_vi)):
        nham = ", ".join(f"{k} ({n})" for k, n in nl.get(r["benh"], [])) or "–"
        md.append(f"| {ten_vi.get(r['benh'], r['benh'])} (`{r['benh']}`) | {r['so_ca']:,} | {pt(r['precision'])} | "
                  f"{pt(r['recall'])} | {pt(r['top3_recall'])} | {nham} |")

    md += ["", "## 4. Bệnh rất nặng (lưới an toàn, đủ evidence)", "",
           "| Bệnh | Số ca | Recall top-1 | Tỷ lệ P ≥ ngưỡng rất nặng |", "|---|---|---|---|"]
    p0 = P["Đủ evidence"]; yy = y[giu]
    for r in theo_tung_benh(p0, yy, lop, sorted(rat_nang)):
        j = lop.index(r["benh"])
        md.append(f"| `{r['benh']}` | {r['so_ca']:,} | {pt(r['recall'])} | {pt(float((p0[yy == j, j] >= ng['rat_nang']).mean()))} |")

    md += ["", "## 5. Quét ngưỡng (giữ 50% evidence – gần với người dùng thật)", "",
           "Dùng bảng này để chọn giá trị `sang_loc.nguong_top1` và `sang_loc.nguong_rat_nang` trong bảng `cau_hinh`.", "",
           "| Ngưỡng top-1 | Ngưỡng rất nặng | Recall cần khám | Bệnh rất nặng lên mức 3 | Báo động thừa | Hiển thị đúng |",
           "|---|---|---|---|---|---|"]
    quet = []
    for t1 in (0.3, 0.4, 0.5, 0.6, 0.7):
        for rn in (0.05, 0.10, 0.20):
            b = bao_cao(P["Giữ 50% evidence"], yy, lop, pham_vi, rat_nang, {**ng, "top1": t1, "rat_nang": rn})
            quet.append({"top1": t1, "rat_nang": rn, **{k: b[k] for k in ("recall_can_kham", "recall_rat_nang_muc3",
                                                                            "bao_dong_thua", "hien_thi_dung")}})
            dang_dung = " **(đang dùng)**" if (t1, rn) == (ng["top1"], ng["rat_nang"]) else ""
            md.append(f"| {t1:.2f}{dang_dung} | {rn:.2f} | {pt(b['recall_can_kham'])} | {pt(b['recall_rat_nang_muc3'])} | "
                      f"{pt(b['bao_dong_thua'])} | {pt(b['hien_thi_dung'])} |")

    ra = Path(a.bao_cao); ra.mkdir(parents=True, exist_ok=True)
    (ra / "danh_gia.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (ra / "danh_gia.json").write_text(json.dumps({"model_version": goi.phien_ban, "ket_qua": BC, "quet_nguong": quet},
                                                 ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Đã ghi {ra / 'danh_gia.md'}")


if __name__ == "__main__":
    main()
