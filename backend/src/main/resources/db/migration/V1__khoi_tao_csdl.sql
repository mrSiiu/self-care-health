-- =====================================================================
-- V1__khoi_tao_csdl.sql  —  PostgreSQL 16
-- Quy ước: UUID cho ID, timestamptz (UTC) cho thời điểm, date cho ngày
-- nghiệp vụ, enum lưu varchar + CHECK (dễ map JPA, dễ thêm giá trị).
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- ---------------------------------------------------------------------
-- 1. NGƯỜI DÙNG
-- ---------------------------------------------------------------------
CREATE TABLE nguoi_dung (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email              varchar(255) NOT NULL,
    mat_khau_bam       varchar(100) NOT NULL,                 -- bcrypt (NFR02)
    ho_ten             varchar(100) NOT NULL,
    vai_tro            varchar(20)  NOT NULL DEFAULT 'NGUOI_DUNG'
                       CHECK (vai_tro IN ('NGUOI_DUNG','QUAN_TRI_NOI_DUNG','ADMIN')),
    trang_thai         varchar(20)  NOT NULL DEFAULT 'CHUA_XAC_THUC'
                       CHECK (trang_thai IN ('CHUA_XAC_THUC','HOAT_DONG','BI_KHOA')),
    so_lan_sai         smallint     NOT NULL DEFAULT 0,
    khoa_den           timestamptz,                           -- khóa tạm sau 5 lần sai
    tao_luc            timestamptz  NOT NULL DEFAULT now(),
    cap_nhat_luc       timestamptz  NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_nguoi_dung_email ON nguoi_dung (lower(email));

-- Token dùng một lần: xác thực email, đặt lại mật khẩu (chỉ lưu hash)
CREATE TABLE token_tai_khoan (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nguoi_dung_id      uuid NOT NULL REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    loai               varchar(20) NOT NULL CHECK (loai IN ('XAC_THUC_EMAIL','DAT_LAI_MAT_KHAU')),
    token_hash         char(64)    NOT NULL UNIQUE,           -- SHA-256 hex
    het_han_luc        timestamptz NOT NULL,
    da_dung_luc        timestamptz
);

CREATE TABLE ho_so_suc_khoe (
    nguoi_dung_id      uuid PRIMARY KEY REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    ngay_sinh          date        NOT NULL,
    gioi_tinh          char(1)     NOT NULL CHECK (gioi_tinh IN ('M','F')),   -- khớp DDXPlus
    dang_mang_thai     boolean     NOT NULL DEFAULT false,
    benh_nen           text,
    di_ung_thuoc       text,
    cap_nhat_luc       timestamptz NOT NULL DEFAULT now(),
    CHECK (NOT dang_mang_thai OR gioi_tinh = 'F')
);

CREATE TABLE nguoi_than (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nguoi_dung_id      uuid NOT NULL REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    ho_ten             varchar(100) NOT NULL,
    email              varchar(255) NOT NULL,
    quan_he            varchar(50)  NOT NULL,
    trang_thai         varchar(20)  NOT NULL DEFAULT 'CHO_XAC_NHAN'
                       CHECK (trang_thai IN ('CHO_XAC_NHAN','DA_XAC_NHAN','HET_HAN','DA_HUY')),
    token_xac_nhan_hash char(64) UNIQUE,
    han_token          timestamptz,                           -- +72 giờ (BR20)
    token_huy_nhan_hash char(64) NOT NULL UNIQUE,             -- link hủy nhận cố định
    dong_y_chia_se     boolean NOT NULL DEFAULT true,
    cho_xem_tom_tat    boolean NOT NULL DEFAULT false,
    xac_nhan_luc       timestamptz,
    tao_luc            timestamptz NOT NULL DEFAULT now()
);
-- Một email không được thêm 2 lần cho cùng người dùng (trừ bản ghi đã hủy)
CREATE UNIQUE INDEX uq_nguoi_than_email ON nguoi_than (nguoi_dung_id, lower(email))
    WHERE trang_thai <> 'DA_HUY';

-- BR20: tối đa 3 người thân chưa hủy. Service kiểm tra trước (báo lỗi
-- thân thiện); trigger là lớp chặn cuối khi có 2 request đồng thời.
CREATE FUNCTION fn_gioi_han_nguoi_than() RETURNS trigger AS $$
BEGIN
    PERFORM 1 FROM nguoi_dung WHERE id = NEW.nguoi_dung_id FOR UPDATE;
    IF (SELECT count(*) FROM nguoi_than
         WHERE nguoi_dung_id = NEW.nguoi_dung_id AND trang_thai <> 'DA_HUY'
           AND id <> NEW.id) >= 3 THEN
        RAISE EXCEPTION 'BR20: toi da 3 nguoi than' USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END $$ LANGUAGE plpgsql;
CREATE TRIGGER trg_gioi_han_nguoi_than
    BEFORE INSERT OR UPDATE OF trang_thai ON nguoi_than
    FOR EACH ROW WHEN (NEW.trang_thai <> 'DA_HUY')
    EXECUTE FUNCTION fn_gioi_han_nguoi_than();

-- ---------------------------------------------------------------------
-- 2. TRI THỨC Y TẾ
-- ---------------------------------------------------------------------
CREATE TABLE benh (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ma_ddxplus         varchar(100) UNIQUE,                   -- NULL với bệnh luật
    ten_vi             varchar(150) NOT NULL,
    ten_en             varchar(150),
    nhom               varchar(30)  NOT NULL CHECK (nhom IN ('HO_HAP','TIEU_HOA','KHAC')),
    nguon              varchar(10)  NOT NULL CHECK (nguon IN ('ML','LUAT')),
    trong_pham_vi      boolean      NOT NULL,                 -- 15 bệnh = true
    muc_mac_dinh       smallint     NOT NULL DEFAULT 1 CHECK (muc_mac_dinh BETWEEN 1 AND 3),
    severity_ddxplus   smallint,                              -- từ release_conditions.json
    rat_nang           boolean      NOT NULL DEFAULT false,   -- lưới an toàn: P ≥ 0,10 → mức 3
    CHECK (nguon = 'LUAT' OR ma_ddxplus IS NOT NULL),
    CHECK (NOT (rat_nang AND trong_pham_vi))
);

CREATE TABLE trieu_chung (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ma_ddxplus         varchar(50) UNIQUE,                    -- vd E_91; NULL nếu chỉ dùng cho luật
    ten_vi             varchar(200) NOT NULL,
    vung_co_the        varchar(30)  NOT NULL
                       CHECK (vung_co_the IN ('TOAN_THAN','DAU_MAT','TAI_MUI_HONG','NGUC_HO_HAP','BUNG_TIEU_HOA','DA','KHAC')),
    kieu_gia_tri       varchar(15)  NOT NULL DEFAULT 'CO_KHONG'
                       CHECK (kieu_gia_tri IN ('CO_KHONG','MOT_LUA_CHON','NHIEU_LUA_CHON','SO')),
    don_vi             varchar(20),                           -- °C, ngày ... khi kieu = SO
    cau_hoi_bo_sung    text,
    thu_tu             smallint NOT NULL DEFAULT 0,
    dang_hien_thi      boolean  NOT NULL DEFAULT true
);

-- Giá trị lựa chọn của triệu chứng dạng phân loại (vd vị trí đau → V_xx)
CREATE TABLE lua_chon_trieu_chung (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id) ON DELETE CASCADE,
    ma_ddxplus         varchar(50),                           -- vd V_10
    nhan_vi            varchar(150) NOT NULL,
    thu_tu             smallint NOT NULL DEFAULT 0,
    UNIQUE (trieu_chung_id, ma_ddxplus)
);

CREATE TABLE benh_trieu_chung (
    benh_id            uuid NOT NULL REFERENCES benh(id) ON DELETE CASCADE,
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id) ON DELETE CASCADE,
    la_dac_trung       boolean NOT NULL DEFAULT false,
    PRIMARY KEY (benh_id, trieu_chung_id)
);

CREATE TABLE dau_hieu_nguy_hiem (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ten_vi             varchar(200) NOT NULL,
    thong_diep         text NOT NULL,
    dang_ap_dung       boolean NOT NULL DEFAULT true
);
-- Một red flag khớp khi TẤT CẢ điều kiện của nó đúng
CREATE TABLE dieu_kien_dau_hieu (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dau_hieu_id        uuid NOT NULL REFERENCES dau_hieu_nguy_hiem(id) ON DELETE CASCADE,
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id),
    toan_tu            varchar(5)  NOT NULL DEFAULT 'CO' CHECK (toan_tu IN ('CO','>=','>','<=','<','=')),
    gia_tri            numeric(6,2)
);

CREATE TABLE luat_sang_loc (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benh_id            uuid NOT NULL REFERENCES benh(id),
    so_goi_y_toi_thieu smallint NOT NULL DEFAULT 1 CHECK (so_goi_y_toi_thieu >= 0),
    muc_xu_ly          smallint NOT NULL CHECK (muc_xu_ly BETWEEN 1 AND 3),
    bat_co_nsaid       boolean  NOT NULL DEFAULT false,       -- sốt xuất huyết (BR14)
    dang_ap_dung       boolean  NOT NULL DEFAULT true,
    phien_ban          integer  NOT NULL DEFAULT 1,
    cap_nhat_luc       timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE dieu_kien_luat (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    luat_id            uuid NOT NULL REFERENCES luat_sang_loc(id) ON DELETE CASCADE,
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id),
    loai               varchar(10) NOT NULL CHECK (loai IN ('BAT_BUOC','GOI_Y','LOAI_TRU')),
    UNIQUE (luat_id, trieu_chung_id)
);

-- Phụ lục B đưa vào dữ liệu (NFR06)
CREATE TABLE nguong_muc_xu_ly (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id),
    thuoc_tinh         varchar(15) NOT NULL CHECK (thuoc_tinh IN ('SO_NGAY','GIA_TRI','CO_MAU','MAT_NUOC')),
    toan_tu            varchar(5)  NOT NULL CHECK (toan_tu IN ('>=','>','=')),
    gia_tri            numeric(6,2) NOT NULL,
    muc_xu_ly          smallint NOT NULL CHECK (muc_xu_ly BETWEEN 2 AND 3),
    mo_ta              varchar(255) NOT NULL,
    dang_ap_dung       boolean NOT NULL DEFAULT true
);

CREATE TABLE nguon_tham_khao (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tieu_de            varchar(300) NOT NULL,
    to_chuc            varchar(150) NOT NULL,
    url                varchar(500),
    nam_ban_hanh       smallint
);

CREATE TABLE huong_dan_cham_soc (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    benh_id            uuid NOT NULL REFERENCES benh(id),
    nen_lam            text NOT NULL,
    nen_an             text NOT NULL,
    nen_tranh          text NOT NULL,
    khi_nao_di_kham    text NOT NULL,
    phien_ban          integer NOT NULL DEFAULT 1,
    dang_hieu_luc      boolean NOT NULL DEFAULT true,
    nguoi_cap_nhat_id  uuid REFERENCES nguoi_dung(id),
    cap_nhat_luc       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (benh_id, phien_ban)
);
-- Mỗi bệnh chỉ 1 phiên bản hướng dẫn đang hiệu lực; bản cũ giữ lại làm lịch sử
CREATE UNIQUE INDEX uq_huong_dan_hieu_luc ON huong_dan_cham_soc (benh_id) WHERE dang_hieu_luc;

CREATE TABLE huong_dan_nguon (
    huong_dan_id       uuid NOT NULL REFERENCES huong_dan_cham_soc(id) ON DELETE CASCADE,
    nguon_id           uuid NOT NULL REFERENCES nguon_tham_khao(id),
    PRIMARY KEY (huong_dan_id, nguon_id)
);

-- ---------------------------------------------------------------------
-- 3. THUỐC  (BR07: không có cột liều dùng)
-- ---------------------------------------------------------------------
CREATE TABLE hoat_chat (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ten                varchar(100) NOT NULL,
    la_nsaid           boolean NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX uq_hoat_chat_ten ON hoat_chat (lower(ten));

CREATE TABLE huong_dan_hoat_chat (
    huong_dan_id       uuid NOT NULL REFERENCES huong_dan_cham_soc(id) ON DELETE CASCADE,
    hoat_chat_id       uuid NOT NULL REFERENCES hoat_chat(id),
    PRIMARY KEY (huong_dan_id, hoat_chat_id)
);

CREATE TABLE thuoc (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    ten_thuong_mai     varchar(150) NOT NULL,
    trong_danh_muc     boolean NOT NULL DEFAULT true,
    nguoi_tao_id       uuid REFERENCES nguoi_dung(id) ON DELETE CASCADE,  -- thuốc tự nhập (UC06-A1)
    CHECK (trong_danh_muc = (nguoi_tao_id IS NULL))
);

CREATE TABLE thuoc_hoat_chat (
    thuoc_id           uuid NOT NULL REFERENCES thuoc(id) ON DELETE CASCADE,
    hoat_chat_id       uuid NOT NULL REFERENCES hoat_chat(id),
    PRIMARY KEY (thuoc_id, hoat_chat_id)
);

CREATE TABLE thuoc_trong_tu (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nguoi_dung_id      uuid NOT NULL REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    thuoc_id           uuid NOT NULL REFERENCES thuoc(id),
    han_su_dung        date NOT NULL,
    trang_thai         varchar(10) NOT NULL CHECK (trang_thai IN ('DANG_DUNG','DU_TRU')),
    da_xac_nhan_trung  boolean NOT NULL DEFAULT false,
    danh_dau_do        boolean NOT NULL DEFAULT false,
    da_nhac_het_han    boolean NOT NULL DEFAULT false,
    tao_luc            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ix_tu_thuoc_dang_dung ON thuoc_trong_tu (nguoi_dung_id) WHERE trang_thai = 'DANG_DUNG';
CREATE INDEX ix_tu_thuoc_han ON thuoc_trong_tu (han_su_dung) WHERE NOT da_nhac_het_han;

-- ---------------------------------------------------------------------
-- 4. THEO DÕI
-- ---------------------------------------------------------------------
CREATE TABLE dot_om (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    nguoi_dung_id      uuid NOT NULL REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    bat_dau            timestamptz NOT NULL,
    ket_thuc           timestamptz,
    trang_thai         varchar(20) NOT NULL
                       CHECK (trang_thai IN ('DANG_THEO_DOI','CAN_KHAM_NGAY','DA_KHOI','DA_DI_KHAM','TU_DONG_DONG')),
    muc_hien_tai       smallint NOT NULL CHECK (muc_hien_tai BETWEEN 1 AND 3),
    co_canh_bao_nsaid  boolean NOT NULL DEFAULT false,
    moc_phan_hoi_cuoi  timestamptz NOT NULL,                  -- BR18
    da_gui_hoi_tham    boolean NOT NULL DEFAULT false,        -- 1 email / khoảng không phản hồi
    so_ngay_nang_hon_lien_tiep smallint NOT NULL DEFAULT 0,
    version            integer NOT NULL DEFAULT 0,            -- optimistic lock (JPA @Version)
    CHECK ((trang_thai IN ('DANG_THEO_DOI','CAN_KHAM_NGAY')) = (ket_thuc IS NULL)),
    CHECK (trang_thai <> 'CAN_KHAM_NGAY' OR muc_hien_tai = 3)
);
-- BR15: mỗi người dùng tối đa 1 đợt ốm đang mở
CREATE UNIQUE INDEX uq_dot_om_dang_mo ON dot_om (nguoi_dung_id)
    WHERE trang_thai IN ('DANG_THEO_DOI','CAN_KHAM_NGAY');
CREATE INDEX ix_dot_om_quet ON dot_om (moc_phan_hoi_cuoi)
    WHERE trang_thai IN ('DANG_THEO_DOI','CAN_KHAM_NGAY');

CREATE TABLE lan_sang_loc (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dot_om_id          uuid NOT NULL REFERENCES dot_om(id) ON DELETE CASCADE,
    thoi_diem          timestamptz NOT NULL DEFAULT now(),
    so_ngay_benh       smallint CHECK (so_ngay_benh >= 0),
    nhiet_do_cao_nhat  numeric(3,1) CHECK (nhiet_do_cao_nhat BETWEEN 34 AND 43),
    muc_xu_ly          smallint NOT NULL CHECK (muc_xu_ly BETWEEN 1 AND 3),
    co_dau_hieu_nguy_hiem boolean NOT NULL DEFAULT false,
    co_canh_bao_nsaid  boolean NOT NULL DEFAULT false,
    ml_trang_thai      varchar(15) NOT NULL
                       CHECK (ml_trang_thai IN ('THANH_CONG','KHONG_GOI','LOI','QUA_THOI_GIAN')),
    ml_thoi_gian_ms    integer,
    phien_ban_mo_hinh  varchar(30)
);
CREATE INDEX ix_lan_sang_loc_dot_om ON lan_sang_loc (dot_om_id, thoi_diem DESC);
CREATE INDEX ix_lan_sang_loc_thoi_diem ON lan_sang_loc (thoi_diem);   -- thống kê UC17

CREATE TABLE trieu_chung_da_chon (
    lan_sang_loc_id    uuid NOT NULL REFERENCES lan_sang_loc(id) ON DELETE CASCADE,
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id),
    lua_chon_id        uuid REFERENCES lua_chon_trieu_chung(id),
    gia_tri_so         numeric(6,2),
    PRIMARY KEY (lan_sang_loc_id, trieu_chung_id)
);

CREATE TABLE ket_qua_benh (
    lan_sang_loc_id    uuid NOT NULL REFERENCES lan_sang_loc(id) ON DELETE CASCADE,
    benh_id            uuid NOT NULL REFERENCES benh(id),
    nguon              varchar(10) NOT NULL CHECK (nguon IN ('ML','LUAT')),
    xac_suat           numeric(5,4) CHECK (xac_suat BETWEEN 0 AND 1),  -- NULL nếu từ luật
    thu_hang           smallint NOT NULL,
    hien_thi           boolean NOT NULL,
    PRIMARY KEY (lan_sang_loc_id, benh_id, nguon)
);

CREATE TABLE lan_sang_loc_dau_hieu (
    lan_sang_loc_id    uuid NOT NULL REFERENCES lan_sang_loc(id) ON DELETE CASCADE,
    dau_hieu_id        uuid NOT NULL REFERENCES dau_hieu_nguy_hiem(id),
    PRIMARY KEY (lan_sang_loc_id, dau_hieu_id)
);

CREATE TABLE nhat_ky (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dot_om_id          uuid NOT NULL REFERENCES dot_om(id) ON DELETE CASCADE,
    thoi_diem          timestamptz NOT NULL DEFAULT now(),
    cam_nhan           varchar(10) NOT NULL CHECK (cam_nhan IN ('DO','NHU_CU','NANG_HON')),
    nhiet_do           numeric(3,1) CHECK (nhiet_do BETWEEN 34 AND 43),
    ghi_chu            varchar(500)
);
CREATE INDEX ix_nhat_ky_dot_om ON nhat_ky (dot_om_id, thoi_diem DESC);

CREATE TABLE nhat_ky_trieu_chung (
    nhat_ky_id         uuid NOT NULL REFERENCES nhat_ky(id) ON DELETE CASCADE,
    trieu_chung_id     uuid NOT NULL REFERENCES trieu_chung(id),
    PRIMARY KEY (nhat_ky_id, trieu_chung_id)
);

-- ---------------------------------------------------------------------
-- 5. THÔNG BÁO (Outbox) — mọi email đi qua bảng này
-- ---------------------------------------------------------------------
CREATE TABLE thong_bao (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    loai               varchar(20) NOT NULL
                       CHECK (loai IN ('XAC_NHAN','HOI_THAM','CANH_BAO','KHAN_CAP',
                                       'NHAC_NHAT_KY','NHAC_HET_HAN','TAI_KHOAN')),
    nguoi_dung_id      uuid NOT NULL REFERENCES nguoi_dung(id) ON DELETE CASCADE,
    nguoi_than_id      uuid REFERENCES nguoi_than(id) ON DELETE CASCADE,  -- NULL: gửi cho chính người dùng
    dot_om_id          uuid REFERENCES dot_om(id) ON DELETE CASCADE,
    email_nhan         varchar(255) NOT NULL,
    khoa_chong_trung   varchar(150) NOT NULL UNIQUE,          -- idempotency, vd HOI_THAM:<dot>:<nt>:<moc>
    gui_luc_du_kien    timestamptz NOT NULL,                  -- hoãn đến 7:00 nếu giờ yên lặng
    trang_thai_gui     varchar(10) NOT NULL DEFAULT 'CHO'
                       CHECK (trang_thai_gui IN ('CHO','DA_GUI','LOI','HUY')),
    so_lan_thu         smallint NOT NULL DEFAULT 0,
    da_gui_luc         timestamptz,
    token_tom_tat_hash char(64) UNIQUE,                       -- link xem tóm tắt (nếu cho phép)
    han_token_tom_tat  timestamptz,
    tao_luc            timestamptz NOT NULL DEFAULT now(),
    CHECK (loai NOT IN ('HOI_THAM','CANH_BAO','KHAN_CAP') OR nguoi_than_id IS NOT NULL)
);
CREATE INDEX ix_thong_bao_cho_gui ON thong_bao (gui_luc_du_kien) WHERE trang_thai_gui = 'CHO';

-- ---------------------------------------------------------------------
-- 6. CẤU HÌNH (UC16, NFR06)
-- ---------------------------------------------------------------------
CREATE TABLE cau_hinh (
    khoa               varchar(60) PRIMARY KEY,
    gia_tri            varchar(100) NOT NULL,
    kieu               varchar(10)  NOT NULL CHECK (kieu IN ('SO','GIO','CHUOI','BOOL')),
    mo_ta              varchar(255) NOT NULL,
    cap_nhat_luc       timestamptz  NOT NULL DEFAULT now(),
    nguoi_cap_nhat_id  uuid REFERENCES nguoi_dung(id)
);

INSERT INTO cau_hinh (khoa, gia_tri, kieu, mo_ta) VALUES
 ('sang_loc.nguong_top1',            '0.50', 'SO',   'Top-1 tối thiểu để hiển thị bệnh ML'),
 ('sang_loc.nguong_rat_nang',        '0.10', 'SO',   'P bệnh rất nặng → mức 3'),
 ('sang_loc.nguong_ngoai_pham_vi',   '0.15', 'SO',   'Tổng P bệnh ngoài phạm vi → mức 2'),
 ('sang_loc.ml_timeout_ms',          '2000', 'SO',   'Quá thời gian thì bỏ qua ML (E2)'),
 ('theo_doi.khong_phan_hoi_muc1_gio','24',   'SO',   'Ngưỡng không phản hồi mức 1'),
 ('theo_doi.khong_phan_hoi_muc2_gio','12',   'SO',   'Ngưỡng không phản hồi mức 2'),
 ('theo_doi.gio_nhac',               '08:00,20:00', 'CHUOI', 'Giờ nhắc ghi nhật ký'),
 ('theo_doi.yen_lang_bat_dau',       '22:00', 'GIO', 'Bắt đầu giờ yên lặng'),
 ('theo_doi.yen_lang_ket_thuc',      '07:00', 'GIO', 'Kết thúc giờ yên lặng'),
 ('theo_doi.tu_dong_dong_ngay',      '14',   'SO',   'Tự đóng đợt ốm (BR17)'),
 ('thuoc.nhac_het_han_ngay',         '30',   'SO',   'Nhắc thuốc sắp hết hạn'),
 ('nguoi_than.han_token_gio',        '72',   'SO',   'Hạn link xác nhận (BR20)'),
 ('he_thong.mui_gio',                'Asia/Ho_Chi_Minh', 'CHUOI', 'Múi giờ tính giờ nhắc, giờ yên lặng');
