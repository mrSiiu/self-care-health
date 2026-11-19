"""Logic dự đoán thuần Python (không phụ thuộc FastAPI) để test dễ."""
from __future__ import annotations

import os
from pathlib import Path

import joblib

from ddx.model import GoiMoHinh

DUONG_DAN_MAC_DINH = Path(__file__).resolve().parents[1] / "models" / "model.joblib"


class BoDuDoan:
    def __init__(self, goi: GoiMoHinh):
        self.goi = goi

    @classmethod
    def tai(cls, duong_dan: str | Path | None = None) -> "BoDuDoan":
        # Chỉ tải file model do chính pipeline train sinh ra (joblib = pickle).
        duong_dan = Path(duong_dan or os.environ.get("MODEL_PATH", DUONG_DAN_MAC_DINH))
        return cls(GoiMoHinh.from_dict(joblib.load(duong_dan)))

    def du_doan(self, evidences: list[str], tuoi: int, gioi_tinh: str) -> dict:
        evidences = list(dict.fromkeys(e.strip() for e in evidences if e and e.strip()))
        bo_qua = self.goi.ma_hoa.token_bi_bo_qua(evidences)
        p = self.goi.xac_suat([evidences], [tuoi], [gioi_tinh])[0]
        thu_tu = p.argsort()[::-1]
        return {
            "model_version": self.goi.phien_ban,
            "probabilities": [{"code": self.goi.lop[i], "p": round(float(p[i]), 4)} for i in thu_tu],
            "ignored": bo_qua,
        }

    def thong_tin(self) -> dict:
        tt = self.goi.thong_tin
        va = tt.get("validate", {})
        return {
            "model_version": self.goi.phien_ban,
            "trained_at": tt.get("trained_at"),
            "algorithm": tt.get("algorithm"),
            "temperature": tt.get("temperature"),
            "n_classes": len(self.goi.lop),
            "n_evidence_tokens": self.goi.ma_hoa.so_cot_evidence,
            "in_scope": tt.get("in_scope"),
            "metrics_validate": {k: {m: v.get(m) for m in ("top1", "top3", "ece", "recall_can_kham")}
                                 for k, v in va.items()},
        }
