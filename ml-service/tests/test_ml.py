"""Test pipeline ML trên dữ liệu giả cùng định dạng DDXPlus.

  python -m pytest -q
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

GOC = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GOC))

from ddx.data import tach_evidences  # noqa: E402
from ddx.features import MaHoaDacTrung, bo_bot_evidence  # noqa: E402
from ddx.metrics import muc_xu_ly  # noqa: E402
from ddx.model import _ap_nhiet_do  # noqa: E402

NG = {"top1": 0.5, "rat_nang": 0.10, "ngoai_pham_vi": 0.15}


@pytest.fixture(scope="session")
def mo_hinh(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ml")
    chay = lambda *args: subprocess.run([sys.executable, *args], cwd=GOC, check=True, capture_output=True)
    chay("scripts/tao_du_lieu_gia.py", "--ra", str(tmp / "data"), "--so-ca", "3000")
    chay("scripts/train.py", "--du-lieu", str(tmp / "data"), "--mo-hinh", "nb,logreg",
         "--ra", str(tmp / "models"), "--bao-cao", str(tmp / "reports"))
    from app.predictor import BoDuDoan
    return BoDuDoan.tai(tmp / "models" / "model.joblib")


# ---- đọc dữ liệu & đặc trưng ------------------------------------------
def test_tach_evidences():
    assert tach_evidences("['E_48', 'E_54_@_V_161', 'E_56_@_7']") == ["E_48", "E_54_@_V_161", "E_56_@_7"]
    assert tach_evidences("[]") == []


def test_ma_hoa_bo_qua_token_la_va_ap_danh_sach_cho_phep():
    mh = MaHoaDacTrung(tan_suat_toi_thieu=1, danh_sach_cho_phep={"E_1", "E_2"}).fit([["E_1", "E_2_@_V_3", "E_9"]])
    assert set(mh.tu_vung) == {"E_1", "E_2_@_V_3"}          # E_9 không nằm trong danh sách giao diện
    X = mh.transform([["E_1", "E_LA"]], [30], ["F"])
    assert X.shape == (1, mh.so_cot) and X.sum() == 3          # E_1 + nhóm tuổi + giới
    assert mh.token_bi_bo_qua(["E_1", "E_LA"]) == ["E_LA"]


def test_bo_bot_evidence_luon_giu_evidence_ban_dau():
    rng = np.random.default_rng(0)
    kq = bo_bot_evidence([["E_1", "E_2", "E_3"]] * 200, ["E_2"] * 200, 0.0, rng)
    assert all(k == ["E_2"] for k in kq)


def test_nhiet_do_giu_tong_bang_1_va_thu_tu():
    p = np.array([[0.7, 0.2, 0.1]])
    for T in (0.5, 1.0, 2.0):
        q = _ap_nhiet_do(p, T)
        assert q.sum() == pytest.approx(1.0) and list(q.argsort()[0]) == [2, 1, 0]


# ---- mô phỏng chuỗi mức xử lý -----------------------------------------
LOP = ["URTI", "GERD", "Pneumonia", "Panic attack"]
TRONG, NANG = {"URTI", "GERD"}, {"Pneumonia"}


@pytest.mark.parametrize("p, muc_mong_doi", [
    ([0.90, 0.05, 0.02, 0.03], 1),   # tự tin, trong phạm vi
    ([0.40, 0.45, 0.05, 0.10], 2),   # top-1 < 0,50 → danh sách rỗng → mức 2
    ([0.60, 0.05, 0.20, 0.15], 3),   # Đ2: lưới an toàn thắng dù top-1 ≥ 0,50
    ([0.70, 0.10, 0.05, 0.15], 2),   # tổng ngoài phạm vi = 0,20 ≥ 0,15
    ([0.05, 0.05, 0.05, 0.85], 2),   # top-1 là bệnh ngoài phạm vi
])
def test_muc_xu_ly(p, muc_mong_doi):
    assert muc_xu_ly(np.array([p]), LOP, TRONG, NANG, NG)[0] == muc_mong_doi


# ---- mô hình đã train --------------------------------------------------
def test_du_doan_dung_hop_dong(mo_hinh):
    kq = mo_hinh.du_doan(["E_91", "E_201", "E_KHONG_CO"], 27, "F")
    ps = [x["p"] for x in kq["probabilities"]]
    assert len(ps) == len(mo_hinh.goi.lop)
    assert ps == sorted(ps, reverse=True)
    assert sum(ps) == pytest.approx(1.0, abs=1e-3)
    assert kq["ignored"] == ["E_KHONG_CO"]
    assert kq["model_version"].startswith("ddx-")


def test_du_doan_hop_ly_tren_ca_ro_rang(mo_hinh):
    # Bộ dữ liệu giả: GERD đặc trưng bởi E_55_@_V_29 + E_140 + E_57_@_3
    kq = mo_hinh.du_doan(["E_55_@_V_29", "E_140", "E_57_@_3"], 35, "M")
    assert kq["probabilities"][0]["code"] == "GERD"


def test_api_fastapi(mo_hinh):
    pytest.importorskip("fastapi")
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient
    import app.main as m
    with TestClient(m.app) as c:
        m.trang_thai["bo"] = mo_hinh
        r = c.post("/predict", json={"evidences": ["E_91"], "age": 27, "sex": "F"})
        assert r.status_code == 200 and len(r.json()["probabilities"]) == len(mo_hinh.goi.lop)
        assert c.post("/predict", json={"evidences": [], "age": 200, "sex": "X"}).status_code == 422
        assert c.get("/health").json()["status"] == "UP"
