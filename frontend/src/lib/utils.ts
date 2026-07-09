/**
 * Parse datetime string từ backend (naive, giờ VN UTC+7) thành Date object đúng.
 * Backend lưu giờ VN, frontend cần parse đúng để hiển thị.
 * - Nếu str cótimezone info (VD: +07:00) → parse trực tiếp
 * - Nếu str là naive (VD: "2026-07-09 05:10:14") → giả định là giờ VN, parse theo local time
 */
export function parseVnDatetime(str: string | null | undefined): Date | null {
  if (!str) return null;

  // Nếu đã cótimezone info → parse trực tiếp
  if (str.includes('+') || str.includes('Z')) {
    return new Date(str);
  }

  // Naive datetime từ backend = giờ VN → append +07:00
  // JavaScript sẽ interpret đúng: Date object sẽ represent đúng thời điểm UTC
  // toLocaleString() sẽ convert về timezone của browser
  return new Date(str + '+07:00');
}

/**
 * Format datetime string từ backend thành chuỗi hiển thị theo locale VN.
 * VD: "05:10:14 9/7/2026"
 */
export function formatVnTime(str: string | null | undefined): string {
  const date = parseVnDatetime(str);
  if (!date) return 'N/A';
  return date.toLocaleString('vi-VN');
}
