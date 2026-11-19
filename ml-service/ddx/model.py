"""Các mô hình ứng viên, hiệu chỉnh nhiệt độ và gói mô hình để lưu/tải."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.naive_bayes import BernoulliNB
from sklearn.neural_network import MLPClassifier

from .features import MaHoaDacTrung


def tao_ung_vien(ten: str, seed: int = 42):
    if ten == "nb":          # mốc cơ sở: nhanh, dễ giải thích
        return BernoulliNB(alpha=1.0)
    if ten == "logreg":      # tuyến tính đa lớp (softmax), xác suất khá chuẩn
        return LogisticRegression(solver="saga", C=1.0, max_iter=200, tol=1e-3)
    if ten == "mlp":         # mạng 1 lớp ẩn, học được tổ hợp triệu chứng
        return MLPClassifier(hidden_layer_sizes=(256,), batch_size=512, learning_rate_init=1e-3,
                             max_iter=30, early_stopping=True, validation_fraction=0.05,
                             n_iter_no_change=3, random_state=seed)
    raise ValueError(f"Mô hình không hỗ trợ: {ten} (chọn nb | logreg | mlp)")


def _ap_nhiet_do(p: np.ndarray, T: float) -> np.ndarray:
    logit = np.log(np.clip(p, 1e-12, 1.0)) / T
    logit -= logit.max(axis=1, keepdims=True)
    e = np.exp(logit)
    return e / e.sum(axis=1, keepdims=True)


def tim_nhiet_do(p_val: np.ndarray, y_val_idx: np.ndarray) -> float:
    """Temperature scaling: chọn T làm nhỏ NLL trên tập validate.

    Ngưỡng nghiệp vụ (0,50 / 0,10 / 0,15) áp lên xác suất, nên xác suất phải
    "đúng nghĩa": P = 0,7 thì khoảng 70% trường hợp là đúng.
    """
    tot, nll_tot = 1.0, np.inf
    for T in np.logspace(-0.7, 1.0, 60):
        q = _ap_nhiet_do(p_val, T)
        nll = -np.log(np.clip(q[np.arange(len(y_val_idx)), y_val_idx], 1e-12, 1)).mean()
        if nll < nll_tot:
            tot, nll_tot = float(T), nll
    return tot


class GoiMoHinh:
    """Thứ được lưu vào model.joblib và được service FastAPI tải lên."""

    def __init__(self, mo_hinh, ma_hoa: MaHoaDacTrung, nhiet_do: float, phien_ban: str, thong_tin: dict):
        self.mo_hinh = mo_hinh
        self.ma_hoa = ma_hoa
        self.nhiet_do = nhiet_do
        self.phien_ban = phien_ban
        self.thong_tin = thong_tin          # ngày train, độ đo, danh sách bệnh ...
        self.lop = [str(c) for c in mo_hinh.classes_]

    def xac_suat(self, ds_evidences, ds_tuoi, ds_gioi) -> np.ndarray:
        X = self.ma_hoa.transform(ds_evidences, ds_tuoi, ds_gioi)
        return _ap_nhiet_do(self.mo_hinh.predict_proba(X), self.nhiet_do)

    def to_dict(self) -> dict:
        return {"mo_hinh": self.mo_hinh, "ma_hoa": self.ma_hoa.to_dict(), "nhiet_do": self.nhiet_do,
                "phien_ban": self.phien_ban, "thong_tin": self.thong_tin}

    @classmethod
    def from_dict(cls, d: dict) -> "GoiMoHinh":
        return cls(d["mo_hinh"], MaHoaDacTrung.from_dict(d["ma_hoa"]), d["nhiet_do"], d["phien_ban"], d["thong_tin"])
