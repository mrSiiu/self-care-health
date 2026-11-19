"""Mã hóa danh sách evidence → vector thưa (multi-hot) + tuổi + giới tính.

- Evidence nhị phân `E_91` và evidence lựa chọn `E_54_@_V_161`, `E_56_@_7`
  đều là một "token" → một cột. Cách này giữ nguyên ý nghĩa của DDXPlus mà
  không cần biết trước kiểu dữ liệu từng câu hỏi.
- Tuổi chia nhóm (one-hot) vì quan hệ tuổi–bệnh không tuyến tính.
- Token chưa từng thấy lúc train bị bỏ qua và được trả ra để API ghi vào
  trường `ignored` (thiết kế mục 2.2).
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp

MOC_TUOI = [1, 5, 15, 30, 45, 60, 75]          # nhóm: <1, 1–4, 5–14, ..., ≥75


def ma_goc(token: str) -> str:
    return token.split("_@_", 1)[0]


class MaHoaDacTrung:
    def __init__(self, tan_suat_toi_thieu: int = 5, danh_sach_cho_phep: set[str] | None = None):
        self.tan_suat_toi_thieu = tan_suat_toi_thieu
        self.danh_sach_cho_phep = danh_sach_cho_phep   # mã gốc E_xx mà giao diện hỏi được
        self.tu_vung: dict[str, int] = {}

    # ---- tên cột ------------------------------------------------------
    @property
    def so_cot_evidence(self) -> int:
        return len(self.tu_vung)

    @property
    def so_cot(self) -> int:
        return self.so_cot_evidence + len(MOC_TUOI) + 1 + 2

    def ten_cot(self) -> list[str]:
        nhom = [f"tuoi<{MOC_TUOI[0]}"] + [f"tuoi>={a}" for a in MOC_TUOI]
        return sorted(self.tu_vung, key=self.tu_vung.get) + nhom + ["gioi_M", "gioi_F"]

    # ---- fit / transform ---------------------------------------------
    def _duoc_dung(self, token: str) -> bool:
        return self.danh_sach_cho_phep is None or ma_goc(token) in self.danh_sach_cho_phep

    def fit(self, ds_evidences: list[list[str]]) -> "MaHoaDacTrung":
        dem: dict[str, int] = {}
        for evs in ds_evidences:
            for t in evs:
                dem[t] = dem.get(t, 0) + 1
        giu = sorted(t for t, n in dem.items() if n >= self.tan_suat_toi_thieu and self._duoc_dung(t))
        self.tu_vung = {t: i for i, t in enumerate(giu)}
        return self

    def transform(self, ds_evidences, ds_tuoi, ds_gioi) -> sp.csr_matrix:
        hang, cot = [], []
        goc_tuoi = self.so_cot_evidence
        goc_gioi = goc_tuoi + len(MOC_TUOI) + 1
        for i, (evs, tuoi, gioi) in enumerate(zip(ds_evidences, ds_tuoi, ds_gioi)):
            for t in set(evs):
                j = self.tu_vung.get(t)
                if j is not None:
                    hang.append(i); cot.append(j)
            hang.append(i); cot.append(goc_tuoi + int(np.searchsorted(MOC_TUOI, tuoi, side="right")))
            if gioi in ("M", "F"):
                hang.append(i); cot.append(goc_gioi + (0 if gioi == "M" else 1))
        du_lieu = np.ones(len(hang), dtype=np.float32)
        return sp.csr_matrix((du_lieu, (hang, cot)), shape=(len(ds_evidences), self.so_cot))

    def token_bi_bo_qua(self, evidences: list[str]) -> list[str]:
        return [t for t in evidences if t not in self.tu_vung]

    # ---- lưu trữ ------------------------------------------------------
    def to_dict(self) -> dict:
        return {"tan_suat_toi_thieu": self.tan_suat_toi_thieu,
                "danh_sach_cho_phep": sorted(self.danh_sach_cho_phep) if self.danh_sach_cho_phep else None,
                "tu_vung": self.tu_vung}

    @classmethod
    def from_dict(cls, d: dict) -> "MaHoaDacTrung":
        m = cls(d["tan_suat_toi_thieu"], set(d["danh_sach_cho_phep"]) if d["danh_sach_cho_phep"] else None)
        m.tu_vung = dict(d["tu_vung"])
        return m


def bo_bot_evidence(ds_evidences, ds_ban_dau, ty_le_giu: float | tuple[float, float], rng: np.random.Generator):
    """Mô phỏng người dùng chỉ khai một phần triệu chứng.

    DDXPlus sinh ca bằng cách hỏi đáp đầy đủ, còn người dùng thật chỉ chọn vài
    triệu chứng nổi bật. Luôn giữ evidence ban đầu (lý do người dùng mở app)
    và ít nhất 1 evidence.
    """
    kq = []
    for evs, bd in zip(ds_evidences, ds_ban_dau):
        p = ty_le_giu if isinstance(ty_le_giu, float) else rng.uniform(*ty_le_giu)
        giu = [t for t in evs if t == bd or rng.random() < p]
        if not giu and evs:
            giu = [evs[int(rng.integers(len(evs)))]]
        kq.append(giu)
    return kq
