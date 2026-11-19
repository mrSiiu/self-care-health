"""Bước 2 – Train và chọn mô hình.

  python scripts/train.py --du-lieu <thư mục DDXPlus>
  # máy yếu: thêm --toi-da-train 300000 để train trên 300k ca ngẫu nhiên

Quy trình:
  1. Đọc train + validate (đủ 49 bệnh — lưới an toàn).
  2. Tăng cường dữ liệu: nhân bản một phần ca train, bỏ bớt evidence ngẫu
     nhiên (giữ 30–80%) để mô hình quen với đầu vào thiếu của người dùng thật.
  3. Train các ứng viên (nb, logreg, mlp), chấm trên validate ở 2 điều kiện:
     đủ evidence và chỉ giữ 50%.
  4. Chọn mô hình có top-1 trung bình 2 điều kiện cao nhất, hiệu chỉnh nhiệt
     độ trên validate, lưu models/model.joblib + model_info.json.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddx.data import doc_cau_hinh, doc_json, doc_tap, giai_pham_vi, giai_rat_nang  # noqa: E402
from ddx.features import MaHoaDacTrung, bo_bot_evidence  # noqa: E402
from ddx.metrics import bao_cao  # noqa: E402
from ddx.model import GoiMoHinh, _ap_nhiet_do, tao_ung_vien, tim_nhiet_do  # noqa: E402

GOC = Path(__file__).resolve().parents[1]


def pt(x):
    return "–" if x is None else f"{x:.2%}"


def chi_so(nhan, lop):
    vi_tri = {c: i for i, c in enumerate(lop)}
    idx = np.array([vi_tri.get(n, -1) for n in nhan])
    return idx, idx >= 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--du-lieu", default=str(GOC.parent / "data/raw"), help="thư mục DDXPlus (mặc định: data/raw ở gốc repo)")
    ap.add_argument("--cau-hinh", default=str(GOC / "config/pham_vi.json"))
    ap.add_argument("--mo-hinh", default="nb,logreg,mlp", help="danh sách ứng viên, cách nhau dấu phẩy")
    ap.add_argument("--toi-da-train", type=int, default=None)
    ap.add_argument("--toi-da-validate", type=int, default=100_000)
    ap.add_argument("--tang-cuong", type=float, default=0.5, help="tỷ lệ ca train được nhân bản có bỏ bớt evidence")
    ap.add_argument("--danh-sach-evidence", default=None,
                    help="file txt, mỗi dòng 1 mã E_xx giao diện hỏi được; bỏ trống = dùng tất cả")
    ap.add_argument("--phien-ban", default=None)
    ap.add_argument("--ra", default=str(GOC / "models"))
    ap.add_argument("--bao-cao", default=str(GOC / "reports"), help="thư mục ghi train.md")
    ap.add_argument("--seed", type=int, default=42)
    a = ap.parse_args()
    rng = np.random.default_rng(a.seed)
    ra = Path(a.ra); ra.mkdir(parents=True, exist_ok=True)
    Path(a.bao_cao).mkdir(parents=True, exist_ok=True)

    cond = doc_json(a.du_lieu, "release_conditions.json")
    ch = doc_cau_hinh(a.cau_hinh)
    ban_do_pham_vi = giai_pham_vi(cond, ch)
    pham_vi = set(ban_do_pham_vi)
    rat_nang, _ = giai_rat_nang(cond, ch)
    rat_nang -= pham_vi

    t0 = time.time()
    tr = doc_tap(a.du_lieu, "train")
    va = doc_tap(a.du_lieu, "validate", a.toi_da_validate)
    if a.toi_da_train and len(tr) > a.toi_da_train:
        chon = rng.choice(len(tr), a.toi_da_train, replace=False)
        tr.evidences = [tr.evidences[i] for i in chon]; tr.tuoi = [tr.tuoi[i] for i in chon]
        tr.gioi_tinh = [tr.gioi_tinh[i] for i in chon]; tr.nhan = [tr.nhan[i] for i in chon]
        tr.evidence_ban_dau = [tr.evidence_ban_dau[i] for i in chon]
    print(f"Đọc dữ liệu: train {len(tr):,}, validate {len(va):,} ({time.time() - t0:.0f}s)")

    # --- tăng cường ---------------------------------------------------
    evs, tuoi, gioi, nhan = list(tr.evidences), list(tr.tuoi), list(tr.gioi_tinh), list(tr.nhan)
    if a.tang_cuong > 0:
        chon = rng.choice(len(tr), int(len(tr) * a.tang_cuong), replace=False)
        evs += bo_bot_evidence([tr.evidences[i] for i in chon], [tr.evidence_ban_dau[i] for i in chon], (0.3, 0.8), rng)
        tuoi += [tr.tuoi[i] for i in chon]; gioi += [tr.gioi_tinh[i] for i in chon]; nhan += [tr.nhan[i] for i in chon]
    print(f"Sau tăng cường: {len(nhan):,} ca")

    cho_phep = None
    if a.danh_sach_evidence:
        cho_phep = {d.strip() for d in Path(a.danh_sach_evidence).read_text(encoding="utf-8").splitlines() if d.strip()}
    ma_hoa = MaHoaDacTrung(danh_sach_cho_phep=cho_phep).fit(evs)
    X = ma_hoa.transform(evs, tuoi, gioi)
    y = np.array(nhan)
    print(f"Ma trận đặc trưng: {X.shape[0]:,} × {X.shape[1]:,} ({ma_hoa.so_cot_evidence} token evidence)")

    va_thieu = bo_bot_evidence(va.evidences, va.evidence_ban_dau, 0.5, np.random.default_rng(a.seed + 1))
    X_va = ma_hoa.transform(va.evidences, va.tuoi, va.gioi_tinh)
    X_va_thieu = ma_hoa.transform(va_thieu, va.tuoi, va.gioi_tinh)

    ket_qua, tot = [], None
    for ten in [m.strip() for m in a.mo_hinh.split(",") if m.strip()]:
        t1 = time.time()
        mh = tao_ung_vien(ten, a.seed).fit(X, y)
        lop = [str(c) for c in mh.classes_]
        y_va, giu = chi_so(va.nhan, lop)
        p_du, p_thieu = mh.predict_proba(X_va[giu]), mh.predict_proba(X_va_thieu[giu])
        bc_du = bao_cao(p_du, y_va[giu], lop, pham_vi, rat_nang, ch["nguong"])
        bc_thieu = bao_cao(p_thieu, y_va[giu], lop, pham_vi, rat_nang, ch["nguong"])
        diem = (bc_du["top1"] + bc_thieu["top1"]) / 2
        dong = {"mo_hinh": ten, "giay_train": round(time.time() - t1, 1), "diem": diem, "du": bc_du, "thieu_50": bc_thieu}
        ket_qua.append(dong)
        print(f"[{ten}] top1 đủ={bc_du['top1']:.4f} thiếu50={bc_thieu['top1']:.4f} "
              f"top3 đủ={bc_du['top3']:.4f} recall_can_kham={bc_du['recall_can_kham']} ({dong['giay_train']}s)")
        if tot is None or diem > tot[0]:
            tot = (diem, ten, mh, lop, giu, y_va, p_du, p_thieu)

    _, ten, mh, lop, giu, y_va, p_du, p_thieu = tot
    T = tim_nhiet_do(np.vstack([p_du, p_thieu]), np.concatenate([y_va[giu], y_va[giu]]))
    sau_du = bao_cao(_ap_nhiet_do(p_du, T), y_va[giu], lop, pham_vi, rat_nang, ch["nguong"])
    sau_thieu = bao_cao(_ap_nhiet_do(p_thieu, T), y_va[giu], lop, pham_vi, rat_nang, ch["nguong"])
    print(f"Chọn {ten}; nhiệt độ T={T:.3f}; ECE validate: {sau_du['ece']:.4f} (đủ) / {sau_thieu['ece']:.4f} (thiếu 50%)")

    bay_gio = datetime.now(timezone.utc)
    phien_ban = a.phien_ban or f"ddx-{bay_gio:%Y.%m.%d}"
    thong_tin = {
        "model_version": phien_ban, "trained_at": bay_gio.isoformat(timespec="seconds"),
        "algorithm": ten, "temperature": T, "n_train": int(X.shape[0]), "n_features": int(X.shape[1]),
        "classes": lop, "in_scope": sorted(pham_vi),
        "in_scope_vi": {k: b["ten_vi"] for k, b in ban_do_pham_vi.items()}, "very_severe": sorted(rat_nang),
        "thresholds": ch["nguong"], "evidence_whitelist": bool(cho_phep),
        "validate": {"full": sau_du, "missing_50": sau_thieu},
        "candidates": [{k: v for k, v in r.items()} for r in ket_qua],
    }
    goi = GoiMoHinh(mh, ma_hoa, T, phien_ban, thong_tin)
    joblib.dump(goi.to_dict(), ra / "model.joblib", compress=3)
    (ra / "model_info.json").write_text(json.dumps(thong_tin, ensure_ascii=False, indent=2), encoding="utf-8")

    bang = ["# Kết quả train – so sánh mô hình (tập validate)", "",
            f"Phiên bản: `{phien_ban}` · train {X.shape[0]:,} ca (gồm tăng cường {a.tang_cuong:.0%}) · "
            f"{X.shape[1]:,} đặc trưng", "",
            "| Mô hình | Thời gian train | Top-1 (đủ) | Top-3 (đủ) | Top-1 (thiếu 50%) | Top-3 (thiếu 50%) | "
            "Recall cần khám (đủ / thiếu) | Báo động thừa (đủ / thiếu) |",
            "|---|---|---|---|---|---|---|---|"]
    for r in ket_qua:
        d, t = r["du"], r["thieu_50"]
        bang.append(f"| {r['mo_hinh']}{' ✅' if r['mo_hinh'] == ten else ''} | {r['giay_train']} s | {pt(d['top1'])} | "
                    f"{pt(d['top3'])} | {pt(t['top1'])} | {pt(t['top3'])} | {pt(d['recall_can_kham'])} / "
                    f"{pt(t['recall_can_kham'])} | {pt(d['bao_dong_thua'])} / {pt(t['bao_dong_thua'])} |")
    bang += ["", f"Mô hình chọn: **{ten}**, nhiệt độ T = {T:.3f}. "
             f"ECE sau hiệu chỉnh: {sau_du['ece']:.4f} (đủ), {sau_thieu['ece']:.4f} (thiếu 50%).", ""]
    (Path(a.bao_cao) / "train.md").write_text("\n".join(bang), encoding="utf-8")
    print(f"Đã lưu {ra / 'model.joblib'} và {Path(a.bao_cao) / "train.md"} (tổng {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
