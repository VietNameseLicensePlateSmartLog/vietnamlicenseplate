# DAC TA USE CASE - He Thong Nhan Dien Bien So Xe ANPR

---

## UC1: DANG NHAP

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC1 |
| **Ten** | Dang nhap |
| **Actor** | Khach vang lai, Nguoi dung, Admin |
| **Precondition** | Chua dang nhap, dang o trang thai khach |
| **Postcondition** | Dang nhap thanh cong, duoc phan quyen theo role |

**Luong chinh:**
1. Nguoi dung truy cap trang dang nhap
2. Nhap username va password
3. He thong kiem tra thong tin trong DB bang users
4. Thanh cong -> Tao session + Token
5. Phan quyen: User -> Bang nguoi dung, Admin -> Bang dieu phoi

**Luong phu:**
- Sai ten tai khoan hoac mat khau: Hien loi "Sai ten tai khoan hoac mat khau", cho phep nhap lai (toi da 5 lan)
- Het han dang nhap: Sau 5 lan sai, hien loi "Het han dang nhap, vui long thu lai sau"

---

## UC2: QUEN MAT KHAU

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC2 |
| **Ten** | Quen mat khau |
| **Actor** | Nguoi dung (da co tai khoan) |
| **Precondition** | Chua dang nhap, co tai khoan nhu da quen MK |
| **Postcondition** | Email dat lai MK da duoc gui |

**Luong chinh:**
1. Nguoi dung nhan "Quen mat khau?" tren trang dang nhap
2. Nhap email dang ky tai khoan
3. He thong kiem tra email co trong DB khong
4. Email hop le -> Tao token xac thuc (het han 15 phut)
5. Gui email chua link dat lai mat khau: `https://domain.com/reset?token=xxx`
6. Thong bao "Vui long kiem tra email"

**Luong phu:**
- Email khong ton tai: Hien thong bao "Khong tim thay tai khoan voi email nay"
- Gui email that bai: Hien loi "Khong gui duoc email, vui long thu lai"

---

## UC3: DAT LAI MAT KHAU

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC3 |
| **Ten** | Dat lai mat khau |
| **Actor** | Nguoi dung (nhan link tu email) |
| **Precondition** | Da nhan email tu UC2, co token hop le |
| **Postcondition** | Mat khau moi duoc cap nhat, co the dang nhap |

**Luong chinh:**
1. Nguoi dung nhan link dat lai MK tu email
2. He thong kiem tra token con han (15 phut)
3. Token hop le -> Hien form dat mat khau moi
4. Nhap mat khau moi + xac nhan
5. Kiem tra: mat khau moi >= 6 ky tu, 2 truong khop
6. Cap nhat mat khau moi vao DB
7. Vo hieu hoa token cu
8. Thong bao "Dat lai mat khau thanh cong" -> Chuyen ve trang dang nhap

**Luong phu:**
- Token het han: Hien loi "Link da het han, vui long gui lai"
- Mat khau khong khop: Hien loi "Mat khau xac nhan khong khop"
- Mat khau qua ngan: Hien loi "Mat khau toi thieu 6 ky tu"

---

## UC4: DANG KY TAI KHOAN

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC4 |
| **Ten** | Dang ky tai khoan |
| **Actor** | Khach vang lai |
| **Precondition** | Chua dang nhap, dang o trang thai khach |
| **Postcondition** | Tai khoan moi duoc tao, cho xac thuc email |

### A. DANG KY

**Luong chinh:**
1. Khach chon "Dang ky tai khoan moi"
2. Nhap thong tin: ho ten, username, email, mat khau, xac nhan mat khau
3. He thong kiem tra:
   - Username da ton tai trong DB chua
   - Email da duoc dung chua
   - Mat khau >= 6 ky tu
   - Mat khau va xac nhan khop
4. Hop le -> Tao tai khoan moi voi role mac dinh la "user", xac_thuc = 0
5. Tao token xac thuc email (het han 24 gio)
6. Gui email xac thuc: `https://domain.com/verify?token=xxx`
7. Thong bao "Vui long kiem tra email de xac thuc tai khoan"

**Luong phu:**
- Username da ton tai: Hien loi "Username da duoc su dung"
- Email da ton tai: Hien loi "Email da duoc dang ky"
- Mat khau khong khop: Hien loi "Mat khau xac nhan khong khop"
- Mat khau qua ngan: Hien loi "Mat khau toi thieu 6 ky tu"

### B. XAC THUC EMAIL

**Luong chinh:**
1. Nguoi dung nhan link xac thuc tu email
2. He thong kiem tra token con han (24 gio)
3. Token hop le -> Cap nhat xac_thuc = 1 trong DB
4. Vo hieu hoa token
5. Thong bao "Xac thuc email thanh cong - Ban co the dang nhap"

**Luong phu:**
- Token het han: Hien loi "Link xac thuc da het han, vui long dang ky lai"
- Token khong hop le: Hien loi "Link xac thuc khong hop le"
- Email da xac thuc truoc do: Thong bao "Tai khoan da duoc xac thuc"

---

## UC5: DANG XUAT

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC5 |
| **Ten** | Dang xuat |
| **Actor** | Nguoi dung, Admin |
| **Precondition** | Da dang nhap |
| **Postcondition** | Session bi xoa, ve trang thai khach vang lai |

**Luong chinh:**
1. Nguoi dung nhan nut "Dang xuat"
2. He thong xoa session hien tai
3. Ghi log dang xuat vao DB
4. Chuyen ve trang chu (trang thai khach)

---

## UC6: XEM CAMERA REALTIME

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC6 |
| **Ten** | Xem camera realtime |
| **Actor** | Nguoi dung, Admin |
| **Precondition** | Camera hoac video source da ket noi |
| **Postcondition** | Hien thi ket qua nhan dien tren khung hinh |

**Luong chinh:**
1. Nguoi dung truy cap trang camera
2. He thong ket noi WebSocket den client
3. Client gui frame anh tu webcam
4. He thong chay pipeline 3-stage YOLO (UC8)
5. Gui ket qua annotated anh ve client
6. Hien thi bien so + confidence tren khung hinh

**Luong phu:**
- Mat ket noi WebSocket: Tu dong ket noi lai
- Khong detect duoc bien so: Hien khung hinh khong co label

---

## UC7: UPLOAD VIDEO DE NHAN DIEN

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC7 |
| **Ten** | Upload video de nhan dien |
| **Actor** | Nguoi dung, Admin |
| **Precondition** | Co file video (MP4) |
| **Postcondition** | Video da xu ly, ket qua duoc xuat ra file va DB |

**Luong chinh:**
1. Nguoi dung chon file video upload
2. He thong doc video, lay FPS va tong so frame
3. Lay mau 2 frame/giay (FRAME_INTERVAL = 0.5s)
4. Moi frame -> chay pipeline 3-stage YOLO (UC8)
5. Theo doi track bien so (UC9)
6. Sau khi het video -> Gop ket qua (UC10)
7. Tinh do tin cay (UC11)
8. Xuat file: plates_log.csv, characters_log.xlsx, video_output.mp4 (UC12)
9. Luu vao Database (UC21)


---

## UC8: XEM LICH SU NHAN DIEN CA NHAN

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC13 |
| **Ten** | Xem lich su nhan dien ca nhan |
| **Actor** | Nguoi dung |
| **Precondition** | Da dang nhap |
| **Postcondition** | Hien thi danh sach bien so da nhan dien |

**Luong chinh:**
1. Nguoi dung truy cap trang lich su
2. He thong truy van DB bang detections (theo user hoac tat ca)
3. Hien thi danh sach: bien so, confidence, thoi gian, anh chup
4. Cho phep loc theo ngay, confidence, bien so

---

## UC9: XAC MINH KET QUA DUNG/SAI

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC14 |
| **Ten** | Xac minh ket qua dung/sai |
| **Actor** | Nguoi dung, Admin |
| **Precondition** | Co ket qua nhan dien can xac minh |
| **Postcondition** | Du lieu ghi vao bang predictions voi is_correct = 1/0 |

**Luong chinh:**
1. Nguoi dung chon ket qua can xac minh
2. Danh dau: Dung (is_correct = 1) hoac Sai (is_correct = 0)
3. He thong ghi vao DB bang predictions:
   - plate_text, predicted_text, is_correct, verified_by, verified_at
4. Cap nhat thong ke ti le dung/sai

**Luong phu:**
- Admin co the xac minh tat ca ket qua
- Nguoi dung chi xac minh ket qua cua minh

---

## UC10: XEM BANG DIEU PHOI (ADMIN DASHBOARD)

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC15 |
| **Ten** | Xem bang dieu phoi |
| **Actor** | Admin / Chu he thong |
| **Precondition** | Da dang nhap voi quyen Admin |
| **Postcondition** | Hien thi tong quan he thong |

**Luong chinh:**
1. Admin truy cap Dashboard
2. He thong doc tu Database
3. Hien thi cac muc:
   - **Tong quan:** Tong lan nhan dien, so bien duy nhat, confidence TB
   - **Nguoi dung:** Danh sach, phan quyen, chan
   - **Ti le du doan:** Dung X%, Sai Y%, Chua xac minh Z%
   - **Thong ke bien so:** Top bien, phan bo confidence, bien bat thuong
   - **Nhat ky:** Log hoat dong

---

## UC11: QUAN LY NGUOI DUNG

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC16 |
| **Ten** | Quan ly nguoi dung |
| **Actor** | Admin / Chu he thong |
| **Precondition** | Da dang nhap voi quyen Admin |
| **Postcondition** | Thay doi duoc thong tin nguoi dung |

**Luong chinh:**
1. Xem danh sach nguoi dung
2. Them nguoi dung moi (username, password, role)
3. Chinh sua thong tin (role, trang thai)
4. Chan / mo chan nguoi dung
5. Xoa nguoi dung

---

## UC12: XEM TI LE DU DOAN DUNG/SAI

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC17 |
| **Ten** | Xem ti le du doan dung/sai |
| **Actor** | Admin / Chu he thong |
| **Precondition** | Da co du lieu xac minh tu UC14 |
| **Postcondition** | Hien thi bieu do va ty le |

**Luong chinh:**
1. Doc du lieu tu bang predictions
2. Tinh toan:
   - Ty le dung = so luong is_correct=1 / tong * 100%
   - Ty le sai = so luong is_correct=0 / tong * 100%
   - Chua xac minh = chua co ban ghi
3. Hien thi bieu do theo thoi gian
4. Loc theo khoang thoi gian, bien so cu the

---

## UC13: THONG KE BIEN SO

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC18 |
| **Ten** | Thong ke bien so |
| **Actor** | Admin / Chu he thong |
| **Precondition** | Da co du lieu nhan dien |
| **Postcondition** | Hien thi thong ke chi tiet |

**Luong chinh:**
1. Top bien so nhan dien nhieu nhat
2. Phan bo confidence (histogram)
3. Bien so bat thuong (confidence thap < 70%)
4. Bien so theo khu vuc / camera
5. Xuat bao cao

---

## UC14: XEM NHAT KY HOAT DONG

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC19 |
| **Ten** | Xem nhat ky hoat dong |
| **Actor** | Admin / Chu he thong |
| **Precondition** | Da dang nhap voi quyen Admin |
| **Postcondition** | Hien thi log hoat dong |

**Luong chinh:**
1. Doc log tu DB
2. Hien thi:
   - Lan dang nhap/dang xuat
   - Lan xac minh du doan
   - Thay doi cai dat he thong
   - Lan nhan dien bien so
3. Loc theo loai hoat dong, thoi gian

---

## UC15: TRA CUU DU LIEU

| Thuoc tinh | Mo ta |
|---|---|
| **ID** | UC21 |
| **Ten** | Tra cuu du lieu tu DB |
| **Actor** | Nguoi dung, Admin |
| **Precondition** | Da dang nhap |
| **Postcondition** | Lay du lieu tu DB de hien thi |

**Luong chinh:**
1. Truy van bang detections theo dieu kien (ngay, bien so, confidence)
2. Truy van bang statistics
3. Truy van bang predictions
4. Tra ve ket qua cho UI hien thi
