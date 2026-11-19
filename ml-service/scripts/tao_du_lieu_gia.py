"""Sinh bộ dữ liệu GIẢ có đúng định dạng DDXPlus để chạy thử pipeline.

KHÔNG dùng kết quả trên dữ liệu này để báo cáo. Mục đích duy nhất: kiểm tra
code đọc file, train, đánh giá, service chạy được trước khi có dữ liệu thật.

  python scripts/tao_du_lieu_gia.py --ra data_gia --so-ca 6000
"""
import argparse
import json
import zipfile
from pathlib import Path

import numpy as np

BENH = {  # tên: (severity, triệu chứng đặc trưng)
    "URTI": (5, ["E_91", "E_201", "E_181", "E_53"]),
    "Viral pharyngitis": (5, ["E_91", "E_77", "E_53"]),
    "Influenza": (4, ["E_91", "E_201", "E_45", "E_53", "E_66"]),
    "Acute rhinosinusitis": (4, ["E_181", "E_55_@_V_101", "E_91"]),
    "Allergic sinusitis": (5, ["E_181", "E_116", "E_204_@_V_10"]),
    "Acute laryngitis": (5, ["E_77", "E_82", "E_201"]),
    "Bronchitis": (4, ["E_201", "E_66", "E_91", "E_55_@_V_29"]),
    "GERD": (5, ["E_55_@_V_29", "E_140", "E_57_@_3"]),
    "Pneumonia": (2, ["E_91", "E_201", "E_66", "E_45", "E_57_@_7"]),
    "Pulmonary embolism": (1, ["E_66", "E_55_@_V_29", "E_57_@_8", "E_4"]),
    "Anaphylaxis": (1, ["E_116", "E_82", "E_4", "E_204_@_V_10"]),
    "Possible NSTEMI / STEMI": (1, ["E_55_@_V_29", "E_57_@_9", "E_4"]),
    "Tuberculosis": (2, ["E_201", "E_91", "E_45", "E_150"]),
    "Panic attack": (3, ["E_4", "E_66", "E_57_@_5"]),
}
NHIEU = ["E_91", "E_201", "E_181", "E_53", "E_77", "E_45", "E_66", "E_116", "E_82", "E_140",
         "E_150", "E_4", "E_55_@_V_29", "E_55_@_V_101", "E_57_@_3", "E_57_@_5", "E_204_@_V_10"]


def evidences_json() -> dict:
    ma = sorted({t.split("_@_")[0] for _, (_, ts) in BENH.items() for t in ts} | {t.split("_@_")[0] for t in NHIEU})
    kq = {}
    for m in ma:
        kieu = "C" if m in ("E_57",) else "M" if m in ("E_55", "E_204") else "B"
        kq[m] = {"name": m, "code_question": m, "question_en": f"Câu hỏi giả {m}?",
                 "question_fr": f"Question {m}?", "is_antecedent": m == "E_150",
                 "default_value": 0 if kieu == "C" else "V_0" if kieu == "M" else 0,
                 "possible-values": list(range(11)) if kieu == "C" else ["V_10", "V_29", "V_101"] if kieu == "M" else [],
                 "value_meaning": {"V_10": {"en": "nose", "fr": "nez"}, "V_29": {"en": "chest", "fr": "poitrine"},
                                   "V_101": {"en": "forehead", "fr": "front"}} if kieu == "M" else {},
                 "data_type": kieu}
    return kq


def sinh_ca(rng, n):
    ten = list(BENH)
    w = np.array([5, 4, 4, 3, 3, 2, 3, 3, 2, 1, 1, 1, 1, 1], float)
    dong = []
    for _ in range(n):
        b = ten[rng.choice(len(ten), p=w / w.sum())]
        dac_trung = BENH[b][1]
        evs = [t for t in dac_trung if rng.random() < 0.8] or [dac_trung[0]]
        evs += [t for t in NHIEU if t not in evs and rng.random() < 0.08]
        tuoi = int(rng.integers(18, 80)) if b != "Possible NSTEMI / STEMI" else int(rng.integers(45, 90))
        gioi = "M" if rng.random() < 0.5 else "F"
        dong.append((tuoi, "[]", gioi, b, str(evs), evs[0]))
    return dong


def ghi_zip(duong_dan: Path, ten_trong: str, dong):
    noi_dung = "AGE,DIFFERENTIAL_DIAGNOSIS,SEX,PATHOLOGY,EVIDENCES,INITIAL_EVIDENCE\n" + "".join(
        f'{a},"{d}",{s},{p},"{e}",{i}\n' for a, d, s, p, e, i in dong)
    with zipfile.ZipFile(duong_dan, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(ten_trong, noi_dung)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ra", default="data_gia")
    ap.add_argument("--so-ca", type=int, default=6000)
    a = ap.parse_args()
    ra = Path(a.ra); ra.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(0)
    cond = {k: {"condition_name": k, "cond-name-eng": k, "cond-name-fr": k, "icd10-id": "X00",
                "severity": s, "symptoms": {t.split("_@_")[0]: {} for t in ts}, "antecedents": {}}
            for k, (s, ts) in BENH.items()}
    (ra / "release_conditions.json").write_text(json.dumps(cond, ensure_ascii=False, indent=1), encoding="utf-8")
    (ra / "release_evidences.json").write_text(json.dumps(evidences_json(), ensure_ascii=False, indent=1), encoding="utf-8")
    for tap, ty_le in (("train", 0.8), ("validate", 0.1), ("test", 0.1)):
        ghi_zip(ra / f"release_{tap}_patients.zip", f"release_{tap}_patients", sinh_ca(rng, int(a.so_ca * ty_le)))
    print(f"Đã sinh dữ liệu giả vào {ra.resolve()}")


if __name__ == "__main__":
    main()
