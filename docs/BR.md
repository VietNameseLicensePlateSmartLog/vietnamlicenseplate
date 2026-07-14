# Business Rules (BR)

**Du an:** Vietnam License Plate Recognition (LPR)  
**Phien ban:** 1.0.0  
**Ngay tao:** 2026-07-10

---

## 1. Quy tac dinh dang bien so xe Viet Nam

### 1.1 Cau truc bien so

Bien so xe Viet Nam co do dai **8-10 ky tu**, theo cu the:

| Vi tri (pos) | Kieu ky tu | Mo ta | Dieu kien |
|---|---|---|---|
| **0** | So (0-9) | Ma tinh (dau tien) | BAT BUOC la so |
| **1** | So (0-9) | Ma tinh (thu hai) | BAT BUOC la so |
| **2** | Chu (A-Z, loai I,O,J,Q,W) | Loai xe | BAT BUOC la chu |
| **3** | Chu hoac So | Phan tach / ky hieu | Bat ky (tuy model) |
| **4+** | So (uu tien) | So dinh danh | uu tien so, chu bi phat nang |

### 1.2 Bo ky tu hop le

**Chu cai hop le tren bien so VN** (loai I, O, J, Q, W):
```
A, B, C, D, E, F, G, H, K, L, M, N, P, R, S, T, U, V, X, Z
```

**Ky tu khong hop le tai vi tri 4 (biển 5 dong):**
```
I, O, J, Q, W
```

### 1.3 Mau bien so pho bien

| Mau | Vi du | Mo ta |
|---|---|---|
| **Co ban (8 ky tu)** | 51A-12345 | 2 so + 1 chu + 4-5 so |
| **Co dau gach** | 29B1-23456 | 2 so + 1 chu + 1 so + gach + 5 so |
| **Khong dau gach** | 16F74438 | 2 so + 1 chu + 1 so + 4 so |
| **Quan doi** | 12A1-23456 | 2 so + chu + so + gach + 5 so |

### 1.4 Regex patterns

```
Pattern co ban:    ^(\d{2})([A-Z])[-.\s]?(\d{4,5})$
Pattern quan doi:  ^(\d{2})([A-Z])(\d{1})[-.\s]?(\d{3,5})$
Pattern mo rong:   2 so + 1 chu + 4+ ky tu (70% la so)
```

### 1.5 Diem dinh format (Format Score)

Moi bien so duoc danh gia theo diem:

| Tieu chi | Diem |
|---|---|
| Do dai = 8 ky tu | +10 |
| Do dai = 9-10 ky tu | +5 |
| Vi tri 0 la so | +5 |
| Vi tri 1 la so | +5 |
| Vi tri 2 la chu hop le | +10 |
| Vi tri 3 la so hoac chu | +3 |
| Vi tri 4+ la so | +2 moi ky tu |
| Vi tri 4+ la chu | +1 moi ky tu |
| Ky tu lai (khong hop le) | -1 moi ky tu |

**Danh gia chat luong:**
- `high`: 8 ky tu, format dung
- `medium`: 9-10 ky tu, format dung
- `low`: Khong match pattern
- `invalid`: Co ky tu `?` (chua xac dinh)

---

## 2. Confidence Thresholds

### 2.1 Nhan dien anh (Image)

| Giai doan | Threshold | Mo ta |
|---|---|---|
| **Stage 1** (CONF_S1_IMG) | 0.6 | Phat hien bien so tren anh goc |
| **Stage 2** (CONF_S2_IMG) | 0.5 | Phat hien ky tu tren anh bien so |
| **Stage 3** (CONF_S3_IMG) | 0.3 | Phan loai tung ky tu |

### 2.2 Nhan dien video / Realtime

| Giai doan | Threshold | Mo ta |
|---|---|---|
| **Stage 1** (CONF_S1_VID) | 0.5 | Phat hien bien so (thap hon vi video kem chat luong) |
| **Stage 2** (CONF_S2_VID) | 0.8 | Phat hien ky tu (cao hon de giam nhieu) |
| **Stage 3** (CONF_S3_VID) | 0.7 | Phan loai ky tu (cao hon de chinh xac) |

### 2.3 NMS (Non-Maximum Suppression)

| Giai doan | IoU Threshold | Mo ta |
|---|---|---|
| **Stage 1** | 0.5 | Loai bo box trung lap phat hien bien so |
| **Stage 2** | 0.3 | Loai bo box trung lap ky tu |

### 2.4 Confidence Calculation

- **Anh (1 frame):** Geometric Mean cua confidence tung ky tu
  ```
  confidence = (conf1 * conf2 * ... * confN) ^ (1/N)
  ```
- **Video/Realtime (nhieu frame):** Geometric Mean cua Position Confidence
  ```
  char_confidence[i] = margin * avg_conf
  confidence = (char_conf[0] * char_conf[1] * ... * char_conf[N]) ^ (1/N)
  ```
  Trong do:
  - `margin = (winner_votes - runner_up_votes) / total_votes`
  - `avg_conf = sum_conf_of_winner / winner_votes`

---

## 3. Tracking Rules (Centroid Tracking + Character Voting)

### 3.1 Tham so chi tiet

| Tham so | Gia tri | Mo ta |
|---|---|---|
| **MISS_THRESHOLD** | 4 | So frame mat tin hieu lien tiep de finalize (~2s o 2 FPS) |
| **MIN_HITS** | 2 | So frame toi thieu phat hien duoc truoc khi finalize |
| **CENTROID_DISTANCE** | 100 | Nguong khoang cach Euclid (backup khi IOU thap) |
| **IOU_THRESHOLD** | 0.3 | Nguong IOU toi thieu de match |
| **MIN_MATCH_SCORE** | 0.25 | Nguong combined score toi thieu de match |

### 3.2 Matching Criteria

Detection match voi track khi:

**Dieu kien BAT BUOC:**
- Text similarity >= 0.5 (neu khong -> tao track moi)

**Combined score:**
```
combined_score = IOU x 40% + TextSimilarity x 40% + CentroidSimilarity x 20%
```

**Match khi:**
- IOU >= 0.3 (IOU threshold), HOAC
- combined_score >= 0.25 (min match score)

### 3.3 Text Similarity

```
text_sim = so ky tu giong o cung vi tri / do dai chuoi dai hon
```
- Bo qua dau gach, dau cham, khoang trang
- Chuyen thanh uppercase truoc khi so sanh

### 3.4 Centroid Distance Similarity

```
cent_dist = sqrt((cx1-cx2)^2 + (cy1-cy2)^2)
cent_sim = max(0, 1.0 - (cent_dist / CENTROID_DISTANCE))
```

### 3.5 Character Voting

Khi mot track duoc tao moi, votes duoc khoi tao tu detection dau tien:
```
char_votes[position][character] = so lan phat hien
char_confs[position][character] = tong confidence
```

Moi frame detect duoc, votes duoc cap nhat:
```
char_votes[pos][char] += 1
char_confs[pos][char] += conf
```

Khi track finalize, ky tu duoc chon la ky tu co nhieu votes nhat o moi vi tri.

### 3.6 Finalized Buffer (Chong trung lap)

| Tham so | Gia tri | Mo ta |
|---|---|---|
| **FINALIZED_BUFFER_TTL** | 5.0 giay | Thoi gian nho track da finalize |
| **FINALIZED_BUFFER_MAX** | 20 | So track toi thieu trong buffer |

Khi detection moi xuat hien:
- Kiem tra voi moi entry trong buffer
- Neu IOU >= 0.3 HOAC text similarity >= 0.8 -> SKIP (da co trong DB roi)

### 3.7 Merge Buffer (Gop track)

| Tham so | Gia tri | Mo ta |
|---|---|---|
| **MERGE_BUFFER_TTL** | 10.0 giay | Thoi gian giu ket qua da merge |
| **MERGE_EDIT_DISTANCE** | 1 | Edit distance toi da de fuzzy merge |
| **MERGE_TIME_GAP** | 2.0 giay | Khoang thoi gian toi da giua 2 track de fuzzy merge |

**Merge logic:**
1. **Exact match (text giong nhau):** Gop votes, giu frame dau tien cu nhat
2. **Fuzzy match (edit_distance <= 1, gap <= 2s):** Gop votes
3. **Khong match:** Tao entry moi

---

## 4. Snapshot Rules

### 4.1 Snapshot Frame Dau Tien

Khi track finalize, he thong dung **frame dau tien** cua track lam anh snapshot verification:
```
Frame 1: "29A12345" conf=0.72 -> luu frame nay lam snapshot
Frame 2: "29A12345" conf=0.89 -> cap nhat votes
Frame 3: "29A12345" conf=0.91 -> cap nhat votes
Frame 4-11: conf giam dan -> giu votes
Frame 12: Bien mat -> finalize
  -> Snapshot: dung frame 1 (anh dau tien khi bien xuat hien)
  -> Confidence: Geometric Mean tu character voting
```

### 4.2 Best Frame Tracking

Moi track luu ca:
- `first_frame_img`: Frame dau tien khi bien xuat hien (dung cho snapshot verification)
- `best_frame_img`: Frame co confidence cao nhat (backup neu first_frame kem)

---

## 5. Auth Rules

### 5.1 Dang ky (Register)

- Username va email la bat buoc, khong duoc trong
- Username da ton tai da verify -> bao loi
- Username da ton tai chua verify -> cap nhat password moi
- Email da duoc tai khoan khac su dung -> bao loi
- Tao user voi `role='user'`, `is_verified=0`, `is_active=True`

### 5.2 OTP Rules

- Ma OTP: 6 ky tu so, dinh dang `{:06d}`
- Thoi han OTP: **5 phut** tu thoi diem tao
- Moi tai khoan chi co 1 OTP hop le (OTP cu bi xoa truoc khi tao moi)
- 2 loai token: `email_verify` (dang ky) va `password_reset` (quen mat khau)

### 5.3 Password Rules

- Hash: PBKDF2-HMAC-SHA256, 100,000 iterations, salt 16 bytes
- Dinh dang hash: `salt_hex:key_hex`
- Mat khau moi khi dat lai KHONG duoc trung mat khau cu
- Mat khau admin mac dinh: `123456` (chi cho phat trien)

### 5.4 Login Rules

- Tai khoan phai `is_verified = 1` (da xac thuc OTP)
- Tai khoan phai `is_active = True` (khong bi vo hieu hoa)
- Dang nhap that bai ghi log hoat dong voi IP address
- Chi ghi log dang nhap khi:
  - Lan dau dang nhap (last_login_at = NULL), HOAC
  - Da dang xuat truoc do (last_logout_at > last_login_at)

### 5.5 Phan quyen (Role-Based Access)

| Role | Quyen |
|---|---|
| **admin** | Toan quyen: quan ly nguoi dung, xac minh, thong ke, nhat ky, phan vung |
| **user** | Nhan dien anh/video/realtime, xem lich su ca nhan, xem phan vung |

### 5.6 Account Protection

- Khong cho xoa tai khoan admin mac dinh `abc1`
- Khi xoa user: xoa tokens, cap nhat activity_logs/detections/video_jobs (SET NULL user_id)

---

## 6. Verification Rules (Xac minh ket qua)

### 6.1 Flow xac minh

1. Admin xem danh sach detections chua xac minh (`/admin/detections/unverified`)
2. Admin bam nut **Dung** hoac **Sai** cho moi detection
3. He thong tao ban ghi `Prediction` voi:
   - `plate_text`: Bien so dung (admin nhap)
   - `predicted_text`: Bien so he thong nhan dien duoc
   - `is_correct`: 1 (dung) hoac 0 (sai)
   - `verified_by`: ID nguoi xac minh

### 6.2 Quy tac xac minh

- Moi detection chi duoc xac minh **1 lan** boi moi nguoi dung
- Khi xac minh: cap nhat `Statistic` hang ngay (correct_count hoac incorrect_count)
- Khi xac minh: giam `unverified_count` di 1
- Khi xac minh: ghi nhat ky hoat dong

### 6.3 Xoa detection

- Xoa ca file snapshot anh tren disk
- Xoa prediction lien quan (neu da verify)
- Cap nhat Statistic hang ngay (giam correct_count hoac incorrect_count)
- Ghi nhat ky hoat dong

---

## 7. Source Types

| Source | Gia tri | Mo ta |
|---|---|---|
| **Camera** | `camera` | Nhan dien thoi gian thuc tu webcam qua WebSocket |
| **Anh** | `image` | Upload anh tinh de nhan dien |
| **Video** | `video` | Upload video de xu ly nen |

---

## 8. Statistics Rules

### 8.1 Statistic Hang Ngay

Moi ngay co 1 ban ghi `Statistic` voi:

| Field | Mo ta |
|---|---|
| `stat_date` | Ngay (unique) |
| `total_detections` | Tong so luot nhan dien |
| `unique_plates` | So bien so duy nhat |
| `avg_confidence` | Confidence trung binh |
| `correct_count` | So luot xac minh dung |
| `incorrect_count` | So luot xac minh sai |
| `unverified_count` | So luot chua xac minh |

### 8.2 Cap nhat Statistics

- Khi xac minh (verify): tang correct_count hoac incorrect_count, giam unverified_count
- Khi xoa detection da verify: giam correct_count hoac incorrect_count
- Su dung mui gio Viet Nam (UTC+7) de xac dinh ngay

---

## 9. Video Processing Rules

### 9.1 Trang thai Video Job

```
pending -> processing -> completed
                   \-> failed
```

### 9.2 Giai doan xu ly

1. **Upload:** Luu file vao temp directory
2. **Init:** Tao VideoJob trong DB voi status="pending"
3. **Background thread:** Chay xu ly trong thread rieng
4. **Processing:** Doc tung frame, nhan dien, tracking, ghi output video
5. **Progress:** Cap nhat progress moi 2 frame (hoac khi het video)
6. **Complete:** Cap nhat status="completed", luu output_video path
7. **Cleanup:** Xoa file input temp

### 9.3 Xu ly loi Video

- **GPU OOM:** Fallback Stage1 xuong 640px, xoa GPU cache
- **VideoWriter fail:** Thu mp4v -> XVID -> tat writer (van xu ly detection)
- **Frame error:** Skip frame, ghi traceback vao file log
- **Disk space < 500MB:** Bao loi, khong xu ly
- **Codec fail:** Fallback tu dong, khong crash he thong

---

## 10. Activity Log Rules

### 10.1 Cac hanh dong duoc ghi

| Hanh dong | Mo ta |
|---|---|
| Dang ky | Tai khoan moi duoc tao |
| Dang nhap | Dang nhap thanh cong |
| Dang nhap that bai | Sai mat khau, tai khoan bi vo hieu hoa |
| Dang xuat | Tai khoan dang xuat |
| Tai len video | Khoi chay xu ly video |
| Xac minh bien so | Danh gia Dung/Sai |
| Tao tai khoan | Admin tao tai khoan moi |
| Doi role | Admin doi role nguoi dung |
| Kich hoat/VO hieu hoa | Admin thay doi trang thai tai khoan |
| Xoa tai khoan | Admin xoa nguoi dung |
| Xoa detection | Xoa ban ghi nhan dien |

### 10.2 Thong tin ghi log

- `user_id`: Nguoi thuc hien (NULL neu admin hanh dong)
- `action`: Ten hanh dong
- `detail`: Mo ta chi tiet
- `ip_address`: Dia chi IP (neu co)
- `created_at`: Thoi gian (auto)
