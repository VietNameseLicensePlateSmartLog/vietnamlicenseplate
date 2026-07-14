# Product Requirements Document (PRD)

**Du an:** Vietnam License Plate Recognition (LPR)  
**Phien ban:** 1.0.0  
**Ngay tao:** 2026-07-10  
**Trang thai:** Hoat dong

---

## 1. Muc tieu du an

### 1.1 Tong quan

Xay dung he thong nhan dien tu dong bien so xe Viet Nam su dung tri tue nhan tao (AI), ho tro nhieu nguon dau vao: webcam thoi gian thuc, anh tinh va video. He thong dung kien truc 3 giai đoạn YOLOv8 (phat hien bien so -> phat hien ky tu -> phan loai ky tu) ket hop Centroid Tracking + Character Voting de dat do chinh xac cao nhat.

### 1.2 Muc tieu cu the

- **Nhan dien tu dong:** Phat hien va doc bien so xe Viet Nam tu webcam, anh va video voi do tin cay cao
- **Thoi gian thuc:** Hien thi ket qua nhan dien ngay lap tuc qua WebSocket khi camera quay
- **Quan ly nguoi dung:** He thong xac thuc OTP qua Gmail, phan quyen Admin/User
- **Quan tri:** Dashboard thong ke tong hop, xac minh ket qua nhan dien, quan ly nguoi dung
- **Phan vung:** Quan ly camera theo khu vực de thong ke theo dia diem
- **Lich su:** Luu tru va quan ly toan bo lich su nhan dien voi bo loc da dang

### 1.3 Doi tuong su dung

| Vai tro | Mo ta | Quyen han |
|---|---|---|
| **Admin** | Quan tri vien he thong | Quyen day du: quan ly nguoi dung, xac minh nhan dien, xem thong ke, xem nhat ky hoat dong, quan ly phan vung |
| **User (Regular)** | Nguoi dung binh thuong da xac thuc OTP | Nhan dien anh/video, xem lich su cua minh, su dung webcam thoi gian thuc |
| **Guest** | Chua dang nhap | Khong co quyen truy cap bat ky tinh nang nao, can dang nhap de su dung |

### 1.4 Success Metrics

| Chi so | Muc tieu | Cach do |
|---|---|---|
| **Confidence Accuracy (Image)** | >= 85% bien so dung tren anh ro | So luong prediction is_correct / tong luot xac minh |
| **Confidence Accuracy (Video/Realtime)** | >= 90% bien so dung (vi Character Voting giam nhieu) | So luong prediction is_correct / tong luot xac minh |
| **Processing Speed (Image)** | < 2 giay/anh | Thoi gian xu ly trung binh tren tap test |
| **Processing Speed (Video)** | Xu ly ~2 FPS (moi frame ~0.5s) | Thoi gian xu ly / tong so frame |
| **WebSocket Latency** | < 500ms tu frame den ket qua | Do tre WebSocket trung binh |
| **User Adoption** | >= 10 nguoi dung dang ky trong 30 ngay | So luong tai khoan da xac thuc OTP |
| **False Positive Rate** | < 5% nhan dien sai bien so hoan toan | So luong detection is_correct=0 / tong |
| **System Uptime** | >= 99% khi hoat dong | Thoi gian khong mat ket noi |

---

## 2. Tinh nang chi tiet

### 2.1 Nhan dien thoi gian thuc (Realtime)

**Mo ta:** Ket noi webcam qua WebSocket, hien thi ket qua nhan dien ngay lap tuc.

**Chi tiet:**
- Ket noi WebSocket den backend qua `/api/v1/ws/lpr`
- Gui frame anh tu webcam (base64) den server
- Su dung Centroid Tracking de theo doi bien so qua cac frame
- Character Voting gop ket qua nhieu frame de tang do chinh xac
- Snapshot frame dau tien: khi track finalize, dung frame dau tien lam anh verification
- Confidence tu voting: tinh bang Geometric Mean tu character voting
- Tu dong luu ket qua vao database khi bien so bien mat (track finalize)
- Hien thi danh sach cac bien dang duoc track (active_plates) de ve bbox live

**Dieu kien track finalize:**
- Miss threshold = 4 frame mat tin hieu lien tiep
- Min hits = 2 (toi thieu 2 frame detect duoc)
- Matching criteria: IOU x 40% + TextSimilarity x 40% + CentroidSimilarity x 20%
- Bat buoc text similarity >= 0.5 de match voi track cu

### 2.2 Nhan dien tu anh (Image Upload)

**Mo ta:** Upload anh (JPG, PNG, BMP, WebP) de nhan dien bien so.

**Chi tiet:**
- Ho tro nhieu dinh dang anh: JPG, JPEG, PNG, BMP, WebP
- Hien thi bounding box, text va confidence score tren anh
- Ve annotated image voi mau sac phan biet tung bien so
- Luu ket qua vao lich su voi source_type="image"
- Snapshot anh voi bounding box duoc luu trong `static/snapshots/`
- Confidence thresholds cho anh: Stage1=0.6, Stage2=0.5, Stage3=0.3

### 2.3 Nhan dien tu video (Video Processing)

**Mo ta:** Upload video (MP4, AVI, MOV, MKV) de xu ly nen trong background thread.

**Chi tiet:**
- Ho tro dinh dang: MP4, AVI, MOV, MKV
- Xu ly nen (background thread) khong blocking API
- Frame skip: xu ly ~2 FPS (moi frame ~0.5s) de tang toc
- Centroid Tracking + Character Voting cho video
- Snapshot video dung frame dau tien cua track
- Theo doi tien trinh xu ly real-time qua polling (`/tasks/{task_id}`)
- Tai video ket qua da annotate
- VideoWriter fault-tolerant: mp4v -> XVID fallback, neu ca hai fail van tiep xu ly detection
- Confidence thresholds cho video: Stage1=0.5, Stage2=0.8, Stage3=0.7
- Giam do phan giai Stage1 cho video: 1024px thay vi 1280px

### 2.4 Xac thuc nguoi dung (Authentication)

**Mo ta:** He thong xac thuc hoan chinh voi OTP qua Gmail.

**Chi tiet:**
- Dang ky tai khoan tai `/signin` (独立 page)
- Dang nhap tai `/login`
- Xac thuc OTP qua Gmail (SMTP)
- Che do Development: OTP in ra console khi SMTP chua kha dung
- Phan quyen Admin / User
- Quen mat khau -> OTP -> Dat lai mat khau (mat khau moi khong duoc trung cu)

**Quy tac mat khau:**
- Mat khau duoc bam bang PBKDF2-HMAC-SHA256 voi 100,000 iterations
- Salt ngau nhien 16 bytes moi lan hash
- Dang nhap that bai ghi nhat ky hoat dong

### 2.5 Quan ly nguoi dung (Admin Dashboard)

**Mo ta:** Dashboard quan tri toan dien voi thong ke, quan ly nguoi dung va xac minh ket qua.

**Chi tiet:**
- Thong ke tong quan: tong luot nhan dien, nguoi dung, phan vung, video
- Biểu do nhan dien theo ngay (7 ngay gan nhat)
- Biểu do ti le theo loai nguon (camera / anh / video)
- Thong ke bien thien confidence theo khu vuc
- Quan ly nguoi dung (tao, sua role, kich hoat/vo hieu hoa, xoa)
- Xac minh ket qua nhan dien: nut Dung / Sai / Xoa (xoa detection khoi database)
- Nhat ky hoat dong (hien thi email nguoi thuc hien)
- Tim kiem detections voi bo loc da dang

### 2.6 Phan vung camera (Region)

**Mo ta:** Quan ly cac phan vung camera de thong ke theo khu vuc.

**Chi tiet:**
- Xem danh sach phan vung camera dang hoat dong
- Gan region khi nhan dien de thong ke theo khu vuc
- 4 phan vung mac dinh: Camera Cổng Chính, Cổng Phụ, Hầm Gửi Xe A, Hầm Gửi Xe B
- Region co fields: name, location, is_active

### 2.7 Lich su nhan dien (History)

**Mo ta:** Xem va quan ly lich su nhan dien.

**Chi tiet:**
- Xem lich su nhan dien voi bo loc theo bien so, nguon, thoi gian, khu vuc
- Xem chi tiet snapshot voi bounding box
- Phan trang
- Xoa ban ghi nhan dien (xoa ca file snapshot tren disk)

---

## 3. Non-functional Requirements

### 3.1 Performance

| Chi so | Yeu cau |
|---|---|
| **Image processing** | < 2 giay/anh tren GPU |
| **Video processing** | >= 2 FPS xu ly (moi frame ~0.5s) |
| **WebSocket response** | < 500ms tu gui frame den nhan ket qua |
| **API response** | < 200ms cho cac endpoint CRUD |
| **Database query** | < 100ms cho cac truy van thong ke |
| **Concurrent users** | Ho tro toi thieu 10 nguoi dung dong thoi |

### 3.2 Security

- **Password hashing:** PBKDF2-HMAC-SHA256 voi 100,000 iterations, salt 16 bytes ngau nhien
- **OTP:** Ma 6 so, het han sau 5 phut, moi tai khoan chi co 1 OTP hop le
- **Xac thuc:** Bắt buoc tai khoan phai duoc xac thuc OTP truoc khi dang nhap
- **Phan quyen:** Admin chi truy cap duoc admin panel, User chi xem lich su cua minh
- **CORS:** Cau hinh cho phep frontend ket noi
- **Rate limiting:** OTP bi xoa truoc khi tao moi (ngan spam)
- **Account protection:** Khong cho xoa tai khoan admin mac dinh `abc1`

### 3.3 Scalability

- **Database:** PostgreSQL 14+ ho tro concurrent connections
- **AI Pipeline:** Singleton pattern, GPU/CPU fallback tu dong
- **Video processing:** Background thread, khong blocking main event loop
- **File storage:** UUID-based snapshot naming, khong trung lap
- **Modular architecture:** MVC pattern, tach biet controller/service/route

### 3.4 Reliability

- **GPU OOM handling:** Automatic fallback to lower resolution, then CPU
- **VideoWriter fault-tolerant:** mp4v -> XVID -> skip writing, van tiep xu ly detection
- **Frame error handling:** Skip frame loi, khong crash toan bo qua trinh
- **Disk space check:** Kiem tra dung luong truoc khi xu ly video (toi thieu 500MB)
- **Database migration:** Soft migration (ALTER TABLE with exception handling)
- **Dev mode:** SMTP chua cau hinh van hoat dong binh thuong voi OTP in console

---

## 4. Constraints

| Rang buoc | Mo ta |
|---|---|
| **Hardware** | GPU NVIDIA (RTX series) khuyen nghi, he thong tu dong fallback CPU |
| **Model weights** | 3 file .pt phai co san trong `backend/weights/` - he thong bao loi neu thieu |
| **SMTP** | Can App Password Gmail (16 ky tu) de gui OTP, khong phai mat khau thuong |
| **Database** | PostgreSQL 14+ phay chay truoc khi start backend |
| **Python** | 3.11+ |
| **Node.js** | 18+ (cho frontend) |
| **Disk space** | Toi thieu 500MB trong khi xu ly video |

---

## 5. Assumptions

1. Nguoi dung co trinh do su dung web cơ ban
2. Camera/smartphone co kha nang gui WebSocket frames
3. Mangu on dinh cho WebSocket ket noi
4. GPU co san tren may chu se duoc su dung, CPU la fallback
5. Dung tai khoan admin mac dinh `abc1/123456` chi cho phat trien, khong dung production

---

## 6. Out of Scope

- Nhan dien bien so quoc te (chi Viet Nam)
- Nhan dien nhieu bien so trong 1 frame (dang ho tro nhung gioi han)
- Xu ly video real-time (chi upload video de xu ly nen)
- Mobile app (chi web app)
- Xu luu tru anh/video luon tuc tren cloud
- Tich hop voi he thong giao thong thong minh
- API public cho third-party
