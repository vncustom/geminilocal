# geminilocal

Một tiện ích GUI nhỏ giúp gọi các mô hình Gemini và các provider AI khác (Google, MegaLLM, Open Router), xử lý văn bản dài bằng cách chia nhỏ, gọi API cho từng phần với cơ chế retry, timeout, và lưu kết quả hợp nhất ra ổ đĩa.

## Tính năng mới

- **Hỗ trợ nhiều provider:** Chọn Google, MegaLLM hoặc Open Router để gọi các mô hình AI khác nhau.
- **Chọn model:** Dropdown cho phép chọn model phù hợp với provider.
- **Xuất kết quả ra PDF/Word:** Menu "Export" cho phép lưu kết quả xử lý thành file PDF hoặc Word.
- **Chia văn bản:** Chia theo chương (regex) hoặc theo số ký tự/số từ, có hỗ trợ tiếng Anh, Trung, Việt.
- **Xử lý song song:** Quá trình xử lý chạy ở background thread, UI luôn phản hồi.
- **Retry & Timeout:** Nếu model chính lỗi hoặc timeout, tự động thử lại với model dự phòng (fallback).
- **Lưu kết quả:** Kết quả từng phần và toàn bộ được lưu vào `~/Downloads/gemini_results/`.

## Sử dụng

1. **Chạy GUI:**
   ```powershell
   python .\gem5.py
   ```

2. **Chọn provider và model:**  
   - Provider: Google, MegaLLM, Open Router.
   - Model: Chọn từ danh sách tương ứng.

3. **Tải API Key:**  
   - Nhấn "Chọn File API Key", chọn file chứa API key (dòng đầu tiên không trống, không phải comment).

4. **Chọn phương thức chia văn bản:**  
   - "Theo chương (第X章/Chương X)" hoặc "Theo số ký tự".
   - Nhập số ký tự/số từ mỗi phần (tùy ngôn ngữ).

5. **Nhập prompt, bối cảnh chương trước (tùy chọn), và văn bản cần xử lý.**

6. **Gửi yêu cầu:**  
   - Nhấn "Gửi yêu cầu", theo dõi tiến trình và kết quả từng phần.

7. **Xuất kết quả:**  
   - Menu "Export" phía trên cho phép lưu kết quả ra PDF hoặc Word.

8. **Tải kết quả mới nhất:**  
   - Nhấn "Tải kết quả mới nhất" để xem lại file kết quả gần nhất.

## Lưu ý

- **Thư mục kết quả:** `~/Downloads/gemini_results/`
- **Yêu cầu:** Python >=3.8, tkinter, google-generative-ai, openai, reportlab, python-docx (cài thêm nếu export Word).
- **Cài đặt:**  
   ```
   pip install google-generative-ai openai reportlab python-docx
   ```

## Troubleshooting

- Nếu gặp lỗi khi export Word, cài thêm `python-docx`.
- Nếu provider MegaLLM hoặc Open Router không hoạt động, kiểm tra API key và base_url.
- Nếu không chia được văn bản, kiểm tra lại định dạng hoặc tăng số ký tự/số từ mỗi phần.

## Đóng góp & mở rộng

- Có thể mở rộng thêm provider, model, hoặc chức năng export khác.
- Nếu cần bổ sung ví dụ, hướng dẫn chi tiết, hoặc test tự động, hãy liên hệ hoặc yêu cầu.

---

_Last updated: October 25, 2025_
