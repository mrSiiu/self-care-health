"""Độ đo mô hình và mô phỏng phần quyết định mức xử lý của backend.

Backend (Chain of Responsibility, thiết kế mục 4.3) mới là nơi quyết định
mức xử lý. Ở đây mô phỏng lại 3 mắt xích dùng xác suất ML để đo chỉ tiêu
"recall nhóm cần đi khám", vì chỉ tiêu này phụ thuộc vào cả mô hình lẫn
ngưỡng:
  10 LuoiAnToan   : P(bệnh rất nặng) ≥ 0,10 → mức 3
  20 NgoaiPhamVi  : tổng P(bệnh ngoài phạm vi) ≥ 0,15 → mức ≥ 2
  30 DoTinCayML   : top-1 ≥ 0,50 và thuộc 8 bệnh → hiển thị; không thì
  99 DanhSachRong : không có bệnh hiển thị → mức ≥ 2
Luật 7 bệnh, red flag và ngưỡng Phụ lục B không mô phỏng ở đây (chúng chỉ
nâng mức), nên kết quả thật của hệ thống an toàn hơn hoặc bằng số đo này.
"""
from __future__ import annotations

import numpy as np


def top_k(p: np.ndarray, y: np.ndarray, k: int) -> float:
    top = np.argsort(-p, axis=1)[:, :k]
    return float((top == y[:, None]).any(axis=1).mean())


def ece(p: np.ndarray, y: np.ndarray, so_khoang: int = 15) -> float:
    """Expected Calibration Error của xác suất top-1."""
    conf, du_doan = p.max(axis=1), p.argmax(axis=1)
    dung = (du_doan == y).astype(float)
    bien = np.linspace(0, 1, so_khoang + 1)
    tong = 0.0
    for a, b in zip(bien[:-1], bien[1:]):
        m = (conf > a) & (conf <= b)
        if m.any():
            tong += m.mean() * abs(dung[m].mean() - conf[m].mean())
    return float(tong)


def muc_xu_ly(p: np.ndarray, lop: list[str], trong_pham_vi: set[str], rat_nang: set[str], nguong: dict) -> np.ndarray:
    idx_trong = np.array([c in trong_pham_vi for c in lop])
    idx_nang = np.array([c in rat_nang for c in lop])
    muc = np.ones(len(p), dtype=int)
    if idx_nang.any():
        muc[(p[:, idx_nang] >= nguong["rat_nang"]).any(axis=1)] = 3
    ngoai = p[:, ~idx_trong].sum(axis=1)
    muc[(ngoai >= nguong["ngoai_pham_vi"]) & (muc < 2)] = 2
    top1 = p.argmax(axis=1)
    hien_thi = idx_trong[top1] & (p.max(axis=1) >= nguong["top1"])
    muc[~hien_thi & (muc < 2)] = 2
    return muc


def bao_cao(p, y_idx, lop, trong_pham_vi, rat_nang, nguong) -> dict:
    y_ten = np.array(lop)[y_idx]
    la_trong = np.isin(y_ten, list(trong_pham_vi))
    la_nang = np.isin(y_ten, list(rat_nang))
    muc = muc_xu_ly(p, lop, trong_pham_vi, rat_nang, nguong)
    kq = {
        "so_ca": int(len(y_idx)),
        "top1": top_k(p, y_idx, 1), "top3": top_k(p, y_idx, 3), "top5": top_k(p, y_idx, 5),
        "ece": ece(p, y_idx),
        "top1_8_benh": top_k(p[la_trong], y_idx[la_trong], 1) if la_trong.any() else None,
        "top3_8_benh": top_k(p[la_trong], y_idx[la_trong], 3) if la_trong.any() else None,
        # an toàn: ca ngoài phạm vi phải được đẩy lên mức ≥ 2
        "recall_can_kham": float((muc[~la_trong] >= 2).mean()) if (~la_trong).any() else None,
        # ca bệnh rất nặng phải lên mức 3
        "recall_rat_nang_muc3": float((muc[la_nang] == 3).mean()) if la_nang.any() else None,
        # cái giá: ca bệnh nhẹ trong phạm vi bị báo đi khám
        "bao_dong_thua": float((muc[la_trong] >= 2).mean()) if la_trong.any() else None,
        # ca trong phạm vi được hiển thị đúng bệnh ở top-1
        "hien_thi_dung": float(((muc[la_trong] == 1) & (p[la_trong].argmax(1) == y_idx[la_trong])).mean())
                         if la_trong.any() else None,
        "phan_bo_muc": {str(m): int((muc == m).sum()) for m in (1, 2, 3)},
    }
    return kq


def theo_tung_benh(p, y_idx, lop, chon: list[str]) -> list[dict]:
    du_doan = p.argmax(axis=1)
    kq = []
    for ten in chon:
        if ten not in lop:
            continue
        j = lop.index(ten)
        that = y_idx == j
        doan = du_doan == j
        tp = int((that & doan).sum())
        kq.append({"benh": ten, "so_ca": int(that.sum()),
                   "precision": tp / doan.sum() if doan.any() else None,
                   "recall": tp / that.sum() if that.any() else None,
                   "top3_recall": top_k(p[that], y_idx[that], 3) if that.any() else None})
    return kq


def nham_lan_nhieu_nhat(p, y_idx, lop, chon: list[str], n: int = 3) -> dict[str, list[tuple[str, int]]]:
    du_doan = p.argmax(axis=1)
    kq = {}
    for ten in chon:
        if ten not in lop:
            continue
        j = lop.index(ten)
        sai = du_doan[(y_idx == j) & (du_doan != j)]
        gia_tri, dem = np.unique(sai, return_counts=True)
        thu_tu = np.argsort(-dem)[:n]
        kq[ten] = [(lop[gia_tri[i]], int(dem[i])) for i in thu_tu]
    return kq
