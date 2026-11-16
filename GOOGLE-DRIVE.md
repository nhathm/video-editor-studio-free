# Dựng video qua Google Drive (từ iPhone)

Dành cho khi bạn điều khiển Claude Code trên máy tính từ điện thoại (Remote Control). File đính kèm từ điện
thoại bị giới hạn khoảng 30 MB, nên video lớn đi qua Google Drive:

| Google Drive | Trên máy tính (workspace) |
|---|---|
| **nve › google-raw-input**: bạn tải video gốc lên đây | `google-drive/google-raw-input/` |
| **nve › google-edited-output**: video đã dựng xuất hiện ở đây | `google-drive/google-edited-output/` |

Có ở cả bản Pro và bản Free, từ **1.0.2**. Chỉ chạy với Claude Code trên máy tính, không có trên claude.ai.
nve không bao giờ xoá file (trên Drive hay trên máy) và không tạo link chia sẻ.

## 1. Update plugin lên 1.0.2 (trên máy tính)

Gõ lần lượt vào ô chat Claude Code (Claude không tự chạy được lệnh `/plugin`):

```
/plugin marketplace update nve-studio
```

Rồi mở `/plugin` → **Installed** → **nve** → **Update** (hoặc trong Terminal: `claude plugin update nve@nve-studio`).
Thoát Claude Code và mở lại.

Muốn tự update về sau: `/plugin` → **Marketplaces** → `nve-studio` → bật auto-update.

## 2. Kiểm tra chắc chắn là 1.0.2

Hai cách, nên làm cả hai:

1. `/plugin` → **Installed** → **nve**: phải ghi version **1.0.2**.
2. Gõ vào chat:
   ```
   /nve chạy nve where và nve drive status, chỉ báo lại version và kết quả
   ```
   Phải thấy `"version": "1.0.2"`. Nếu Claude báo không có lệnh `drive` (`invalid choice: 'drive'`) là vẫn
   đang chạy bản cũ: làm lại bước 1 và nhớ mở lại Claude Code.

Lưu ý: nếu trong danh sách skill có **hai** `nve` (plugin và skill đã lưu trên claude.ai từ điện thoại), bản
có Drive là **plugin**. Skill trên claude.ai không update theo plugin và không có Drive.

## 3. Kết nối Google Drive (một lần cho mỗi máy tính, phải ngồi ở máy)

```
/nve setup-gg-drive
```

Một cửa sổ trình duyệt mở ra trên máy tính: đăng nhập Google và bấm **Allow** (có 5 phút). Xong, Claude báo
hai thư mục trên Drive đã sẵn sàng. Quyền truy cập chỉ lưu trên máy tính đó, nên **máy khác phải làm lại bước
này**. Không làm được từ điện thoại vì cần đăng nhập trên chính máy tính.

Nên để máy tính không ngủ (Remote Control mới kết nối được): Cài đặt hệ thống → Màn hình khoá / Pin → tắt tự
ngủ khi cắm sạc, hoặc dùng app như Amphetamine.

## 4. Tải video từ iPhone lên Drive

Trong app **Google Drive** trên iPhone:

1. Tab **Tệp** (Files) → mở thư mục **nve** → **google-raw-input**.
2. Bấm nút **+** → **Tải lên** (Upload) → **Ảnh và video** → chọn video → **Tải lên**.
3. Chờ tới khi hết vòng tải (xem ở thanh tiến trình). Video lớn nên dùng Wi-Fi và để app mở tới khi xong.

Cách khác: trong app **Ảnh**, chọn video → nút Chia sẻ → **Drive** → chọn thư mục **nve › google-raw-input**
→ Tải lên.

Muốn dựng một video đã có sẵn ở chỗ khác trên Drive: bấm **⋯** trên file → **Chia sẻ** → **Sao chép liên kết**,
rồi dán link vào chat ở bước 5.

## 5. Xem danh sách file trong Claude Code

Từ Remote Control trên điện thoại, gõ:

```
/nve xem video trên Drive
```

Claude liệt kê các file trong **nve › google-raw-input** (tên · dung lượng · ngày, mới nhất trước) và cho biết
file nào đã có trên máy.

## 6. Tải file về và dựng như bình thường

- Một file: `/nve dựng video IMG_3049.MOV trên Drive` (đúng tên file như trong danh sách).
- Nhiều file: `/nve dựng video từ Drive: số 1 và số 3`.
- Bằng link: `/nve dựng video này <dán link Drive>`.
- Chỉ có một file trong thư mục: `/nve dựng video trên Drive` là đủ.

Claude tải file về máy (video lớn mất vài phút), rồi dựng như bình thường: hỏi style, cho xem kế hoạch, ảnh
preview, render. Khi xong, video (và ảnh cover) được đưa lên **Drive › nve › google-edited-output**, Claude
báo đường dẫn, ví dụ "Xong: Drive › nve › google-edited-output › promo.mp4". Mở app Drive trên iPhone để xem
hoặc tải về.

Muốn kết quả lên Drive dù video gốc gửi kiểu khác: nói thêm "gửi kết quả lên Drive".

## Khi có lỗi

| Claude báo | Làm gì |
|---|---|
| Drive chưa kết nối | Ngồi ở máy tính, gõ `/nve setup-gg-drive` |
| Hết quyền Google / mất mạng | Kiểm tra mạng; nếu vẫn lỗi, `/nve setup-gg-drive` lại ở máy tính |
| Đăng nhập không xong / quá giờ | `/nve setup-gg-drive` lại, bấm **Allow** trong 5 phút |
| Không thấy file | Kiểm tra tên so với danh sách ở bước 5 (file đã tải lên xong chưa) |
| Link không phải file Drive | Lấy link bằng **Chia sẻ → Sao chép liên kết** trên chính file video |
