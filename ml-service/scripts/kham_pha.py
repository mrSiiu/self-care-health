"""Bước 1 – Khám phá DDXPlus: đếm ca 49 bệnh, xem severity, thống kê evidence.

  python scripts/kham_pha.py --du-lieu <thư mục DDXPlus>

Đầu ra (thư mục reports/):
  kham_pha.md        tóm tắt để đưa vào báo cáo
  benh_ddxplus.csv   49 bệnh: số ca từng tập, severity, trong phạm vi, rất nặng
  evidences.csv      mọi evidence + tần suất + cột ten_vi để dịch (đầu vào V3)
"""
import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ddx.data import doc_cau_hinh, doc_json, doc_tap, giai_pham_vi, giai_rat_nang  # noqa: E402
from ddx.features import ma_goc  # noqa: E402

GOC = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--du-lieu", default=str(GOC.parent / "data/raw"), help="thư mục DDXPlus (mặc định: data/raw ở gốc repo)")
    ap.add_argument("--cau-hinh", default=str(GOC / "config/pham_vi.json"))
    ap.add_argument("--ra", default=str(GOC / "reports"))
    a = ap.parse_args()
    ra = Path(a.ra); ra.mkdir(exist_ok=True)

    cond = doc_json(a.du_lieu, "release_conditions.json")
    evid = doc_json(a.du_lieu, "release_evidences.json")
    ch = doc_cau_hinh(a.cau_hinh)
    pham_vi = giai_pham_vi(cond, ch)
    rat_nang, chieu = giai_rat_nang(cond, ch)
    rat_nang -= set(pham_vi)

    dem_benh, dem_ev, so_ev, tuoi, gioi, tong = {}, Counter(), [], [], Counter(), {}
    for tap in ("train", "validate", "test"):
        ds = doc_tap(a.du_lieu, tap)
        tong[tap] = len(ds)
        dem_benh[tap] = Counter(ds.nhan)
        if tap == "train":
            for evs in ds.evidences:
                dem_ev.update(evs)
                so_ev.append(len(evs))
            tuoi, gioi = ds.tuoi, Counter(ds.gioi_tinh)
        print(f"Đã đọc {tap}: {len(ds):,} ca")

    la_ngoai = [k for k in cond if k not in dem_benh["train"]]
    with open(ra / "benh_ddxplus.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ma_ddxplus", "ten_en", "ten_fr", "severity", "so_ca_train", "so_ca_validate", "so_ca_test",
                    "trong_pham_vi", "ten_vi", "rat_nang"])
        for k in sorted(cond, key=lambda k: -dem_benh["train"][k]):
            c = cond[k]
            w.writerow([k, c.get("cond-name-eng", ""), c.get("cond-name-fr", ""), c.get("severity", ""),
                        dem_benh["train"][k], dem_benh["validate"][k], dem_benh["test"][k],
                        k in pham_vi, pham_vi.get(k, {}).get("ten_vi", ""), k in rat_nang])

    with open(ra / "evidences.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ma", "kieu", "la_tien_su", "cau_hoi_en", "gia_tri", "so_lan_train", "ten_vi", "hien_thi_tren_app"])
        dem_goc = Counter()
        for t, n in dem_ev.items():
            dem_goc[ma_goc(t)] += n
        for m, e in sorted(evid.items(), key=lambda kv: -dem_goc[kv[0]]):
            nghia = e.get("value_meaning") or {}
            gia_tri = "; ".join(f"{v}={(nghia.get(str(v)) or {}).get('en', v)}" for v in e.get("possible-values", []))
            w.writerow([m, e.get("data_type"), e.get("is_antecedent"), e.get("question_en", ""), gia_tri,
                        dem_goc[m], "", ""])

    tb = sum(so_ev) / max(len(so_ev), 1)
    kieu = Counter(e.get("data_type") for e in evid.values())
    tien_su = sum(1 for e in evid.values() if e.get("is_antecedent"))
    dong = [
        "# Khám phá dữ liệu DDXPlus", "",
        f"- Số ca: train **{tong['train']:,}**, validate **{tong['validate']:,}**, test **{tong['test']:,}**",
        f"- Số bệnh: **{len(cond)}**; evidence: **{len(evid)}** (B={kieu.get('B', 0)}, C={kieu.get('C', 0)}, "
        f"M={kieu.get('M', 0)}; tiền sử={tien_su})",
        f"- Số evidence trung bình mỗi ca (train): **{tb:.1f}** (min {min(so_ev)}, max {max(so_ev)})",
        f"- Tuổi: {min(tuoi)}–{max(tuoi)}; giới: {dict(gioi)}",
        f"- Thang severity: {chieu}. Bệnh rất nặng được chọn ({len(rat_nang)}): {', '.join(sorted(rat_nang))}",
        "", "## 8 bệnh trong phạm vi ML", "",
        "| Bệnh | Mã DDXPlus | Severity | Train | Validate | Test | Tỷ lệ train |", "|---|---|---|---|---|---|---|"]
    for k, b in pham_vi.items():
        n = dem_benh["train"][k]
        dong.append(f"| {b['ten_vi']} | `{k}` | {cond[k].get('severity')} | {n:,} | {dem_benh['validate'][k]:,} | "
                    f"{dem_benh['test'][k]:,} | {n / tong['train']:.1%} |")
    n8 = sum(dem_benh["train"][k] for k in pham_vi)
    dong += ["", f"8 bệnh chiếm **{n8 / tong['train']:.1%}** ca train; phần còn lại là lớp \"ngoài phạm vi\" "
             "mà mô hình vẫn phải học để làm lưới an toàn.", ""]
    if la_ngoai:
        dong.append(f"> Bệnh có trong release_conditions.json nhưng không có ca train: {la_ngoai}")
    dong += ["", "## Evidence xuất hiện nhiều nhất (train)", "", "| Evidence | Số lần |", "|---|---|"]
    dong += [f"| `{t}` | {n:,} |" for t, n in dem_ev.most_common(15)]
    (ra / "kham_pha.md").write_text("\n".join(dong) + "\n", encoding="utf-8")
    print(f"Xong. Xem {ra / 'kham_pha.md'}")


if __name__ == "__main__":
    main()
