"""Đọc bộ dữ liệu DDXPlus (Figshare 20043374).

Các file cần có trong thư mục dữ liệu:
  release_conditions.json, release_evidences.json,
  release_train_patients(.csv|.zip), release_validate_patients(.csv|.zip),
  release_test_patients(.csv|.zip)

Mỗi dòng bệnh nhân có các cột: AGE, SEX, PATHOLOGY, EVIDENCES,
INITIAL_EVIDENCE, DIFFERENTIAL_DIAGNOSIS. Cột EVIDENCES là chuỗi dạng
"['E_48', 'E_54_@_V_161', ...]".
"""
from __future__ import annotations

import json
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

TEN_TAP = {"train": "release_train_patients",
           "validate": "release_validate_patients",
           "test": "release_test_patients"}
COT_CAN = ["AGE", "SEX", "PATHOLOGY", "EVIDENCES", "INITIAL_EVIDENCE"]


def tim_file_benh_nhan(thu_muc: Path, tap: str) -> Path:
    goc = TEN_TAP[tap]
    for ung_vien in (thu_muc / f"{goc}.csv", thu_muc / f"{goc}.zip", thu_muc / goc):
        if ung_vien.is_file():
            return ung_vien
    # Kaggle tự giải nén dataset: có thể thành thư mục release_x/release_x hoặc lồng sâu hơn
    for ung_vien in sorted(thu_muc.rglob(f"{goc}*")):
        if ung_vien.is_file() and ung_vien.suffix in ("", ".csv", ".zip"):
            return ung_vien
    raise FileNotFoundError(
        f"Không thấy '{goc}.csv' hoặc '{goc}.zip' trong {thu_muc}. "
        "Hãy đặt các file DDXPlus đã tải vào thư mục này.")


def _doc_csv(duong_dan: Path, so_dong: int | None) -> pd.DataFrame:
    if duong_dan.suffix == ".zip":
        with zipfile.ZipFile(duong_dan) as z:
            ten = [n for n in z.namelist() if not n.endswith("/") and "__MACOSX" not in n]
            if len(ten) != 1:
                raise ValueError(f"{duong_dan} phải chứa đúng 1 file CSV, thấy: {ten}")
            with z.open(ten[0]) as f:
                return pd.read_csv(f, usecols=COT_CAN, nrows=so_dong)
    return pd.read_csv(duong_dan, usecols=COT_CAN, nrows=so_dong)


def tach_evidences(chuoi: str) -> list[str]:
    """Nhanh hơn ast.literal_eval khoảng 7 lần, đủ cho 1,3 triệu dòng."""
    chuoi = chuoi.strip()
    if chuoi in ("[]", ""):
        return []
    # sys.intern: hàng triệu chuỗi "E_91" trùng nhau chỉ giữ 1 bản trong RAM
    return [sys.intern(t.strip().strip("'\"")) for t in chuoi[1:-1].split(",") if t.strip()]


@dataclass
class TapDuLieu:
    evidences: list[list[str]]
    tuoi: list[int]
    gioi_tinh: list[str]
    nhan: list[str]
    evidence_ban_dau: list[str]

    def __len__(self) -> int:
        return len(self.nhan)


def doc_tap(thu_muc: str | Path, tap: str, so_dong: int | None = None) -> TapDuLieu:
    df = _doc_csv(tim_file_benh_nhan(Path(thu_muc), tap), so_dong)
    return TapDuLieu(
        evidences=[tach_evidences(s) for s in df["EVIDENCES"].astype(str)],
        tuoi=df["AGE"].astype(int).tolist(),
        gioi_tinh=df["SEX"].astype(str).str.upper().tolist(),
        nhan=df["PATHOLOGY"].astype(str).tolist(),
        evidence_ban_dau=df["INITIAL_EVIDENCE"].astype(str).tolist(),
    )


def doc_json(thu_muc: str | Path, ten: str) -> dict:
    duong_dan = Path(thu_muc) / ten
    if not duong_dan.is_file():
        tim = sorted(p for p in Path(thu_muc).rglob(ten) if p.is_file())
        if not tim:
            raise FileNotFoundError(f"Không thấy {ten} trong {thu_muc}")
        duong_dan = tim[0]
    with open(duong_dan, encoding="utf-8") as f:
        return json.load(f)


def doc_cau_hinh(duong_dan: str | Path) -> dict:
    with open(duong_dan, encoding="utf-8") as f:
        return json.load(f)


def _cac_ten(khoa: str, tt: dict) -> set[str]:
    ten = {khoa, tt.get("condition_name", ""), tt.get("cond-name-eng", ""), tt.get("cond-name-fr", "")}
    return {t.strip().lower() for t in ten if t}


def tim_khoa_benh(conditions: dict, ten_khop: list[str]) -> str | None:
    """Trả khóa trong release_conditions.json (cũng là giá trị cột PATHOLOGY)."""
    muc_tieu = {t.lower() for t in ten_khop}
    for khoa, tt in conditions.items():
        if _cac_ten(khoa, tt) & muc_tieu:
            return khoa
    return None


def giai_pham_vi(conditions: dict, cau_hinh: dict) -> dict[str, dict]:
    """Ánh xạ 8 bệnh trong phạm vi → khóa DDXPlus thật. Báo lỗi rõ nếu thiếu."""
    kq, thieu = {}, []
    for benh in cau_hinh["trong_pham_vi_ml"]:
        khoa = tim_khoa_benh(conditions, benh["ten_khop"])
        if khoa is None:
            thieu.append(benh["ma_noi_bo"])
        else:
            kq[khoa] = benh
    if thieu:
        raise ValueError(f"Không tìm thấy trong release_conditions.json: {thieu}. "
                         f"Các khóa hiện có: {sorted(conditions)}")
    return kq


def giai_rat_nang(conditions: dict, cau_hinh: dict) -> tuple[set[str], str]:
    """Chọn các bệnh rất nặng theo severity. Tự dò chiều thang severity."""
    rn = cau_hinh["rat_nang"]
    sev = {k: int(v["severity"]) for k, v in conditions.items() if "severity" in v}
    nang = [sev[k] for t in rn["moc_nang"] if (k := tim_khoa_benh(conditions, [t])) in sev]
    nhe = [sev[k] for t in rn["moc_nhe"] if (k := tim_khoa_benh(conditions, [t])) in sev]
    if not nang or not nhe:
        raise ValueError("Không dò được chiều thang severity: thiếu bệnh mốc trong dữ liệu.")
    mot_la_nang_nhat = sum(nang) / len(nang) < sum(nhe) / len(nhe)
    cac_bac = sorted(set(sev.values()), reverse=not mot_la_nang_nhat)
    bac_chon = set(cac_bac[: rn["so_bac_nang_nhat"]])
    chieu = "1 = nặng nhất" if mot_la_nang_nhat else "số lớn = nặng nhất"
    return {k for k, s in sev.items() if s in bac_chon}, chieu
