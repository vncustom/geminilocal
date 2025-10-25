import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import google.generativeai as genai
import os
import time
import re
from datetime import datetime
import threading
import queue
import concurrent.futures # Thêm thư viện để xử lý timeout
# --- Thư viện cho export PDF/Word ---
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.units import inch

# --- Hằng số mới ---
FALLBACK_MODEL = "gemini-2.5-flash-lite"
API_TIMEOUT_SECONDS = 7 * 60 # 7 phút
# --- Kết thúc hằng số mới ---

class GeminiInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Gemini Pro v5 API Interface (with Retry)") # Cập nhật title
        self.root.geometry("800x900")

        self.root.option_add('*Font', ('Arial', 12))
        if os.name == 'nt':
            self.root.option_add('*Dialog.msg.font', ('Arial', 12))

        self.processing = False
        self.should_stop = False
        self.queue = queue.Queue()
        self.api_key = None  # Initialize API key as None

        self.create_menu_export() # Thêm menu Export phía trên cùng
        self.create_main_frame()
        self.create_widgets()
        self.setup_periodic_queue_check()
    def create_menu_export(self):
        menubar = tk.Menu(self.root)
        export_menu = tk.Menu(menubar, tearoff=0)
        export_menu.add_command(label="Export to PDF", command=self.export_to_pdf)
        export_menu.add_command(label="Export to Word", command=self.export_to_word)
        menubar.add_cascade(label="Export", menu=export_menu)
        self.root.config(menu=menubar)

    def export_to_pdf(self):
        try:
            # Lấy nội dung file kết quả mới nhất
            results_dir = os.path.join(os.path.expanduser("~"), "Downloads", "gemini_results")
            if not os.path.exists(results_dir):
                messagebox.showwarning("Không có dữ liệu", "Thư mục 'gemini_results' không tồn tại.")
                return
            files = [f for f in os.listdir(results_dir) if f.startswith("gemini_result_") and f.endswith(".txt")]
            if not files:
                messagebox.showwarning("Không có dữ liệu", "Không tìm thấy file kết quả nào trong thư mục 'gemini_results'.")
                return
            files.sort(reverse=True)
            latest_file = files[0]
            latest_file_path = os.path.join(results_dir, latest_file)
            with open(latest_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                messagebox.showwarning("Không có dữ liệu", "File kết quả rỗng.")
                return
            # Chọn nơi lưu file PDF
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialdir=os.path.expanduser("~")
            )
            if not file_path:
                return
            # Tạo PDF
            doc = SimpleDocTemplate(file_path, pagesize=letter)
            styles = getSampleStyleSheet()
            # Tạo style tùy chỉnh cho tiêu đề
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                textColor='black',
                spaceAfter=12,
                alignment=1  # Center alignment
            )
            # Tạo style cho nội dung
            body_style = ParagraphStyle(
                'CustomBody',
                parent=styles['BodyText'],
                fontSize=11,
                leading=14,
                spaceAfter=6
            )
            # Xây dựng danh sách các phần tử cho PDF
            elements = []
            elements.append(Paragraph("Gemini Processing Results", title_style))
            elements.append(Spacer(1, 0.3*inch))
            # Thêm nội dung
            for line in content.split('\n'):
                if line.strip():
                    elements.append(Paragraph(line, body_style))
                else:
                    elements.append(Spacer(1, 0.1*inch))
            # Xây dựng PDF
            doc.build(elements)
            messagebox.showinfo("Thành công", f"Đã export sang PDF:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Lỗi khi export sang PDF: {str(e)}")

    def export_to_word(self):
        try:
            from docx import Document
        except ImportError:
            messagebox.showerror("Thiếu thư viện", "Vui lòng cài đặt python-docx: pip install python-docx")
            return
        # Lấy nội dung file kết quả mới nhất
        results_dir = os.path.join(os.path.expanduser("~"), "Downloads", "gemini_results")
        if not os.path.exists(results_dir):
            messagebox.showwarning("Không có dữ liệu", "Thư mục 'gemini_results' không tồn tại.")
            return
        files = [f for f in os.listdir(results_dir) if f.startswith("gemini_result_") and f.endswith(".txt")]
        if not files:
            messagebox.showwarning("Không có dữ liệu", "Không tìm thấy file kết quả nào trong thư mục 'gemini_results'.")
            return
        files.sort(reverse=True)
        latest_file = files[0]
        latest_file_path = os.path.join(results_dir, latest_file)
        try:
            with open(latest_file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
        except Exception as e:
            messagebox.showerror("Lỗi đọc file", f"Không thể đọc file kết quả: {str(e)}")
            return
        if not content:
            messagebox.showwarning("Không có dữ liệu", "File kết quả rỗng.")
            return
        # Chọn nơi lưu file Word
        file_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("Word files", "*.docx")],
            title="Chọn nơi lưu file Word"
        )
        if not file_path:
            return
        try:
            doc = Document()
            for line in content.splitlines():
                doc.add_paragraph(line)
            doc.save(file_path)
            messagebox.showinfo("Thành công", f"Đã xuất ra Word: {file_path}")
        except Exception as e:
            messagebox.showerror("Lỗi xuất Word", str(e))

    def create_main_frame(self):
        self.main_canvas = tk.Canvas(self.root)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical",
                                     command=self.main_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.main_canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )

        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.main_canvas.bind_all("<MouseWheel>",
                                lambda e: self.main_canvas.yview_scroll(
                                    int(-1*(e.delta/120)), "units"))

        self.scrollbar.pack(side="right", fill="y")
        self.main_canvas.pack(side="left", fill="both", expand=True)

    def create_text_widget(self, parent, height=4):
        text_widget = tk.Text(parent, height=height, font=('Arial', 12),
                            wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        text_widget.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        return text_widget

    def create_widgets(self):
        main_container = ttk.Frame(self.scrollable_frame, padding="10")
        main_container.pack(fill="both", expand=True)

        # Language selection
        lang_frame = ttk.LabelFrame(main_container, text="Chọn ngôn ngữ", padding="5")
        lang_frame.pack(fill="x", pady=5)
        self.language = ttk.Combobox(lang_frame, values=["中文", "ENG", "Việt Nam"],
                                   font=('Arial', 12))
        self.language.set("中文")
        self.language.pack(fill="x")
        self.language.bind("<<ComboboxSelected>>", self.on_language_change)

        # Model selection
        model_frame = ttk.LabelFrame(main_container, text="Chọn model chính", padding="5") # Sửa label
        model_frame.pack(fill="x", pady=5)
        # Cập nhật danh sách model nếu cần
        models = ["gemini-2.0-flash-lite-preview-02-05", "gemini-2.5-pro-preview-05-06","gemini-2.0-flash", "gemini-2.5-pro-exp-03-25", "gemini-2.0-flash", "gemini-2.5-pro", "gemini-2.5-flash-preview-04-17", "gemini-2.5-flash-preview-05-20", "gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash-lite", "gemini-2.5-flash-lite"] # Ví dụ cập nhật model
        self.model = ttk.Combobox(model_frame, values=models, font=('Arial', 12))
        self.model.set("gemini-2.5-flash") # Đặt model mặc định mới nếu cần
        self.model.pack(fill="x")

        # API Key Frame
        api_frame = ttk.LabelFrame(main_container, text="API Key", padding="5")
        api_frame.pack(fill="x", pady=5)

        self.api_key_label = ttk.Label(api_frame, text="Chưa có API Key nào được chọn", font=('Arial', 12))
        self.api_key_label.pack(fill="x")

        self.browse_api_key_button = ttk.Button(api_frame, text="Chọn File API Key", command=self.browse_api_key_file)
        self.browse_api_key_button.pack(fill="x", pady=5)

        # Split method
        split_frame = ttk.LabelFrame(main_container,
                                   text="Phương thức chia văn bản",
                                   padding="5")
        split_frame.pack(fill="x", pady=5)
        self.split_method = ttk.Combobox(split_frame,
                                       values=["Theo chương (第X章/Chương X)",
                                              "Theo số ký tự"],
                                       font=('Arial', 12))
        self.split_method.set("Theo chương (第X章/Chương X)")
        self.split_method.pack(fill="x")

        # Split length input
        split_length_frame = ttk.Frame(main_container)
        split_length_frame.pack(fill="x", pady=5)
        self.split_length_label = ttk.Label(split_length_frame, text="Số ký tự/số từ mỗi phần:")
        self.split_length_label.pack(side=tk.LEFT)
        self.split_length_entry = ttk.Entry(split_length_frame, font=('Arial', 12))
        self.split_length_entry.pack(side=tk.LEFT, fill="x", expand=True)
        self.split_length_entry.insert(0, "10000") # Tăng giá trị mặc định nếu muốn

        # Progress bar
        self.progress_bar = ttk.Progressbar(main_container, orient="horizontal",
                                          mode="determinate")
        self.progress_bar.pack(fill="x", pady=5)

        # Prompt input
        prompt_frame = ttk.LabelFrame(main_container, text="Nhập prompt", padding="5")
        prompt_frame.pack(fill="x", pady=5)
        self.prompt_text = self.create_text_widget(prompt_frame, height=4)

        # Additional text input
        additional_frame = ttk.LabelFrame(main_container,
                                        text="Nhập văn bản cần xử lý", # Sửa label
                                        padding="5")
        additional_frame.pack(fill="x", pady=5)
        self.additional_text = self.create_text_widget(additional_frame, height=10) # Tăng chiều cao

        # Buttons
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill="x", pady=10)
        self.submit_button = ttk.Button(button_frame, text="Gửi yêu cầu",
                                      command=self.start_processing)
        self.submit_button.pack(side=tk.LEFT, padx=5)
        self.stop_button = ttk.Button(button_frame, text="Dừng",
                                    command=self.stop_processing, state='disabled') # Bắt đầu ở trạng thái disabled
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.load_button = ttk.Button(button_frame, text="Tải kết quả mới nhất", # Sửa label
                                    command=self.load_results)
        self.load_button.pack(side=tk.LEFT, padx=5)

        # Progress display
        progress_frame = ttk.LabelFrame(main_container, text="Tiến trình xử lý hiện tại",
                                      padding="5")
        progress_frame.pack(fill="x", pady=5)
        self.progress_text = self.create_text_widget(progress_frame, height=2)

        # Current result display
        result_frame = ttk.LabelFrame(main_container, text="Kết quả xử lý phần hiện tại",
                                    padding="5")
        result_frame.pack(fill="x", pady=5)
        self.result_text = self.create_text_widget(result_frame, height=4)

        # Completion status
        completion_frame = ttk.LabelFrame(main_container, text="Kết quả cuối cùng và trạng thái", # Sửa label
                                        padding="5")
        completion_frame.pack(fill="x", pady=5)
        self.completion_text = self.create_text_widget(completion_frame, height=4) # Tăng chiều cao

    def on_language_change(self, event):
        """Update label when language changes."""
        language = self.language.get()
        if language == "ENG":
            self.split_length_label.config(text="Số từ mỗi phần:")
        elif language in ["中文", "Việt Nam"]:
            self.split_length_label.config(text="Số ký tự mỗi phần:")
        else:
            self.split_length_label.config(text="Số ký tự/số từ mỗi phần:")

    def setup_periodic_queue_check(self):
        def check_queue():
            try:
                while True:
                    message = self.queue.get_nowait()
                    widget, text, clear = message
                    if clear:
                        widget.delete("1.0", tk.END)
                    widget.insert(tk.END, text)
                    widget.see(tk.END) # Auto scroll to bottom
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Lỗi UI update: {e}") # Log lỗi UI
            finally:
                self.root.after(100, check_queue)
        self.root.after(100, check_queue)

    def update_ui(self, widget, message, clear=True):
        # Hàm này có thể không cần thiết nữa vì logic đã chuyển vào check_queue
        # Nhưng vẫn giữ lại nếu có chỗ khác dùng
        self.queue.put((widget, message, clear))

    def show_error(self, message):
        # Hiển thị lỗi trên result_text và messagebox
        self.queue.put((self.result_text, f"Lỗi: {message}\n", True))
        messagebox.showerror("Lỗi", message)

    def browse_api_key_file(self):
        """Open file dialog to select API key file."""
        file_path = filedialog.askopenfilename(
            title="Chọn File API Key",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    # Đọc tất cả các dòng và tìm dòng không trống đầu tiên
                    key_found = False
                    for line in f:
                        stripped_line = line.strip()
                        if stripped_line and not stripped_line.startswith('#'): # Bỏ qua dòng trống và comment
                            self.api_key = stripped_line
                            key_found = True
                            break
                if not key_found:
                    self.api_key_label.config(text="File API Key không chứa key hợp lệ")
                    self.api_key = None
                else:
                    self.api_key_label.config(text=f"Đã tải API Key từ: {os.path.basename(file_path)}")
            except Exception as e:
                self.api_key_label.config(text=f"Lỗi đọc file API Key: {str(e)}")
                self.api_key = None

    def validate_inputs(self):
        errors = []

        if not self.api_key:
            errors.append("API Key chưa được tải. Vui lòng chọn file API Key.")

        if not self.prompt_text.get("1.0", tk.END).strip():
            errors.append("Prompt không được để trống")

        if not self.additional_text.get("1.0", tk.END).strip():
            errors.append("Văn bản cần xử lý không được để trống") # Sửa thông báo lỗi

        if self.split_method.get() == "Theo số ký tự":
            try:
                split_length = int(self.split_length_entry.get())
                if split_length <= 0:
                    errors.append("Số ký tự/số từ mỗi phần phải lớn hơn 0")
            except ValueError:
                errors.append("Số ký tự/số từ không hợp lệ")

        return errors

    def start_processing(self):
        if self.processing:
            messagebox.showwarning("Đang xử lý", "Một yêu cầu đang được xử lý. Vui lòng đợi.")
            return

        errors = self.validate_inputs()
        if errors:
            self.show_error("\n".join(errors))
            return

        self.processing = True
        self.should_stop = False
        self.submit_button.configure(state='disabled')
        self.stop_button.configure(state='normal')
        # Xóa các ô text trước khi bắt đầu
        self.progress_text.delete("1.0", tk.END)
        self.result_text.delete("1.0", tk.END)
        self.completion_text.delete("1.0", tk.END)
        self.progress_bar["value"] = 0

        thread = threading.Thread(target=self._process_request_thread, daemon=True)
        # thread.daemon = True # Đã set ở trên
        thread.start()

    def stop_processing(self):
        if not self.processing:
            return
        self.should_stop = True
        self.queue.put((self.progress_text, "\nĐang yêu cầu dừng...", False)) # Ghi thêm, không xóa
        self.stop_button.configure(state='disabled') # Vô hiệu hóa ngay khi bấm dừng

    # --- Hàm gọi API mới ---
    def _call_gemini_api(self, model_name, prompt_content):
        """Hàm thực hiện gọi API thực tế."""
        try:
            # Mỗi lần gọi có thể cần model object mới nếu có cấu hình khác nhau
            # Hoặc đảm bảo model object thread-safe nếu dùng chung
            model_instance = genai.GenerativeModel(model_name)
            response = model_instance.generate_content(prompt_content)
            if not response or not response.text:
                # Đôi khi API trả về response nhưng không có text
                return None, f"Không nhận được nội dung hợp lệ từ model {model_name}"
            return response.text, None # Trả về text và không có lỗi
        except Exception as e:
            # Bắt tất cả lỗi từ API call
            error_msg = f"Lỗi API khi gọi model {model_name}: {type(e).__name__} - {str(e)}"
            print(error_msg) # Log lỗi ra console để debug
            return None, error_msg # Trả về None và thông báo lỗi

    # --- Hàm gọi API với Retry và Timeout ---
    def call_gemini_with_retry_and_timeout(self, primary_model_name, prompt_content):
        """Gọi API với timeout, retry bằng model fallback nếu cần."""
        start_time = time.time()
        error_message_final = "Không có lỗi"

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            # --- Lần thử 1: Model chính ---
            future = executor.submit(self._call_gemini_api, primary_model_name, prompt_content)
            try:
                print(f"Attempting primary model: {primary_model_name}")
                result_text, error_message = future.result(timeout=API_TIMEOUT_SECONDS)
                if error_message: # Lỗi API trả về từ _call_gemini_api
                    print(f"Primary model failed: {error_message}")
                    error_message_final = error_message
                    # Không return ngay, đi tiếp để retry
                else: # Thành công
                    print(f"Primary model success.")
                    return result_text, None # Thành công, trả về kết quả

            except concurrent.futures.TimeoutError:
                elapsed = time.time() - start_time
                print(f"Primary model timeout after {elapsed:.2f}s")
                error_message_final = f"Model chính ({primary_model_name}) timeout sau {elapsed:.2f} giây."
                # Không return ngay, đi tiếp để retry
            except Exception as e: # Các lỗi khác không mong muốn
                 elapsed = time.time() - start_time
                 print(f"Primary model unexpected error after {elapsed:.2f}s: {e}")
                 error_message_final = f"Lỗi không xác định với model chính ({primary_model_name}): {str(e)}"
                 # Không return ngay, đi tiếp để retry

        # --- Nếu đến đây, lần thử 1 đã thất bại (lỗi hoặc timeout) ---
        print(f"Trying fallback model: {FALLBACK_MODEL}")
        self.queue.put((self.progress_text, f"\n-> Thử lại với model {FALLBACK_MODEL}...", False))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
             # --- Lần thử 2: Model fallback ---
            fallback_start_time = time.time()
            future = executor.submit(self._call_gemini_api, FALLBACK_MODEL, prompt_content)
            try:
                result_text, error_message = future.result(timeout=API_TIMEOUT_SECONDS)
                if error_message: # Lỗi API từ fallback model
                    print(f"Fallback model failed: {error_message}")
                    # Kết hợp lỗi gốc và lỗi fallback
                    error_message_final += f"\nRetry với {FALLBACK_MODEL} cũng thất bại: {error_message}"
                    return None, error_message_final # Thất bại hoàn toàn
                else: # Fallback thành công
                     elapsed_fallback = time.time() - fallback_start_time
                     print(f"Fallback model success after {elapsed_fallback:.2f}s.")
                     self.queue.put((self.progress_text, f"\n-> Retry với {FALLBACK_MODEL} thành công.", False))
                     return result_text, None # Thành công với fallback

            except concurrent.futures.TimeoutError:
                elapsed = time.time() - fallback_start_time
                print(f"Fallback model timeout after {elapsed:.2f}s")
                error_message_final += f"\nRetry với {FALLBACK_MODEL} cũng timeout sau {elapsed:.2f} giây."
                return None, error_message_final # Thất bại hoàn toàn
            except Exception as e:
                 elapsed = time.time() - fallback_start_time
                 print(f"Fallback model unexpected error after {elapsed:.2f}s: {e}")
                 error_message_final += f"\nLỗi không xác định khi retry với {FALLBACK_MODEL}: {str(e)}"
                 return None, error_message_final # Thất bại hoàn toàn


    def _process_request_thread(self):
        try:
            genai.configure(api_key=self.api_key)
            primary_model_name = self.model.get()
            # Không cần tạo model instance ở đây nữa vì hàm gọi API sẽ tạo

            prompt = self.prompt_text.get("1.0", tk.END).strip()
            text = self.additional_text.get("1.0", tk.END).strip()

            chapters = self.split_text(text)
            if not chapters:
                self.show_error("Không thể chia văn bản thành các phần.")
                self.processing = False # Đặt lại trạng thái
                self.root.after(0, lambda: self.submit_button.configure(state='normal'))
                self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
                return

            results_dir = os.path.join(os.path.expanduser("~"), "Downloads",
                                     "gemini_results")
            os.makedirs(results_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            result_file = os.path.join(results_dir,
                                     f"gemini_result_{timestamp}_{primary_model_name.replace('/','-')}.txt") # Thay / để tránh lỗi path

            self.progress_bar["maximum"] = len(chapters)
            self.progress_bar["value"] = 0

            status_messages = [] # List để lưu trạng thái từng phần
            total_parts = len(chapters)

            for i, chapter in enumerate(chapters, 1):
                if self.should_stop:
                    status_messages.append(f"Phần {i}/{total_parts}: Đã dừng bởi người dùng.")
                    self.queue.put((self.completion_text,
                                    f"Xử lý đã bị dừng ở phần {i}.\n" + "\n".join(status_messages) + f"\nKết quả chưa hoàn chỉnh lưu tại: {result_file}", True))
                    break

                self.queue.put((self.progress_text,
                              f"Đang xử lý phần {i}/{total_parts}\n"
                              f"Model chính: {primary_model_name}\n"
                              f"Nội dung đầu: {chapter[:100]}...", True))
                self.queue.put((self.result_text, f"--- Đang chờ kết quả phần {i} ---", True))

                full_prompt = f"{prompt}\n\n{chapter}" # Thêm dòng trống để phân tách rõ ràng

                # Gọi hàm mới có retry và timeout
                response_text, error_msg = self.call_gemini_with_retry_and_timeout(
                    primary_model_name, full_prompt
                )

                # Kiểm tra dừng lại lần nữa sau khi gọi API (có thể mất thời gian)
                if self.should_stop:
                     status_messages.append(f"Phần {i}/{total_parts}: Đã dừng bởi người dùng sau khi gọi API.")
                     self.queue.put((self.completion_text,
                                    f"Xử lý đã bị dừng ở phần {i}.\n" + "\n".join(status_messages) + f"\nKết quả chưa hoàn chỉnh lưu tại: {result_file}", True))
                     break

                if error_msg:
                    # Xử lý lỗi sau khi đã retry
                    error_log = f"LỖI PHẦN {i}: {error_msg}"
                    print(error_log) # Log lỗi ra console
                    self.queue.put((self.result_text, error_log, True)) # Hiển thị lỗi ở ô kết quả hiện tại
                    status_messages.append(f"Phần {i}/{total_parts}: Thất bại - {error_msg.splitlines()[0]}") # Chỉ lấy dòng đầu của lỗi cho status

                    # Ghi lỗi vào file kết quả
                    try:
                        with open(result_file, 'a', encoding='utf-8') as f:
                            f.write(f"## LỖI PHẦN {i} ##\n")
                            f.write(f"{error_msg}\n\n")
                    except Exception as write_err:
                        print(f"Không thể ghi lỗi vào file: {write_err}")
                        status_messages[-1] += " (Không ghi được file)" # Cập nhật status

                    # Cập nhật thanh tiến trình và trạng thái tổng thể
                    self.progress_bar["value"] = i
                    self.queue.put((self.completion_text, "\n".join(status_messages) + f"\nKết quả đang lưu tại: {result_file}", True))

                    # Quan trọng: Tiếp tục vòng lặp để xử lý phần tiếp theo
                    continue # Bỏ qua phần bị lỗi, làm phần tiếp theo

                else:
                    # Xử lý thành công
                    self.queue.put((self.result_text,
                                  f"Kết quả xử lý phần {i}:\n{response_text}", True))
                    status_messages.append(f"Phần {i}/{total_parts}: Hoàn thành.")

                    # Ghi kết quả vào file
                    try:
                        with open(result_file, 'a', encoding='utf-8') as f:
                            f.write(f"## ") # Thêm đánh dấu đầu mỗi chương
                            f.write(response_text + "\n\n")
                    except Exception as write_err:
                         print(f"Không thể ghi kết quả phần {i} vào file: {write_err}")
                         status_messages[-1] = f"Phần {i}/{total_parts}: Hoàn thành (Lỗi ghi file)" # Cập nhật status

                    # Cập nhật thanh tiến trình và trạng thái tổng thể
                    self.progress_bar["value"] = i
                    self.queue.put((self.completion_text, "\n".join(status_messages) + f"\nKết quả đang lưu tại: {result_file}", True))

                    # Delay giữa các phần thành công (nếu cần và không bị dừng)
                    if i < total_parts and not self.should_stop:
                        # Có thể bỏ delay hoặc giảm bớt nếu API cho phép tần suất cao hơn
                        # time.sleep(5) # Giảm delay ví dụ còn 5 giây
                        pass # Bỏ delay nếu không cần

            # Kết thúc vòng lặp (hoàn thành hoặc bị dừng)
            final_status = "\n".join(status_messages)
            if not self.should_stop:
                final_status = "Hoàn thành xử lý tất cả các phần.\n" + final_status
                self.queue.put((self.progress_text, "Đã xử lý xong!", True))
            else:
                 final_status = "Xử lý bị dừng.\n" + final_status

            self.queue.put((self.completion_text, final_status + f"\nKết quả đầy đủ (hoặc chưa hoàn chỉnh) lưu tại: {result_file}", True))

        except FileNotFoundError as e:
             self.show_error(f"Lỗi đường dẫn hoặc file: {str(e)}")
        except Exception as e:
            # Bắt các lỗi không mong muốn khác trong quá trình xử lý chính
            error_traceback = traceback.format_exc() # Lấy traceback chi tiết
            print(f"Lỗi nghiêm trọng trong _process_request_thread: {error_traceback}")
            self.show_error(f"Lỗi không xác định trong quá trình xử lý: {str(e)}")
            self.queue.put((self.completion_text, f"Đã xảy ra lỗi nghiêm trọng: {str(e)}", True))

        finally:
            # Đảm bảo trạng thái được reset và nút được kích hoạt lại
            self.processing = False
            # Sử dụng root.after(0, ...) để đảm bảo chúng chạy trên main thread
            self.root.after(0, lambda: self.submit_button.configure(state='normal'))
            self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
            print("Processing thread finished.") # Log kết thúc thread

    def split_text(self, text):
        try:
            split_method = self.split_method.get()
            language = self.language.get()
            split_length = 0 # Khởi tạo
            if split_method == "Theo số ký tự":
                try:
                    split_length = int(self.split_length_entry.get())
                    if split_length <= 0:
                        raise ValueError("Số ký tự/số từ mỗi phần phải lớn hơn 0")
                except ValueError:
                     # Show error và trả về None để dừng xử lý sớm
                     self.show_error("Số ký tự/số từ không hợp lệ.")
                     return None

            if split_method == "Theo chương (第X章/Chương X)":
                # Regex tìm "第...章" hoặc "Chương <số>" hoặc "Chapter <số>" case-insensitive
                # Hỗ trợ cả số La Mã (I, V, X, L, C, D, M) trong Chapter
                pattern = r'(?:第.*?章|Chương\s*\d+|Chapter\s*(?:\d+|[IVXLCDM]+))\b'
                # Sử dụng re.split để tách dựa trên pattern, giữ lại delimiter
                parts = re.split(f'({pattern})', text, flags=re.IGNORECASE)

                if len(parts) <= 1: # Không tìm thấy chương nào
                    # Thử tìm các dấu hiệu xuống dòng kép làm phân tách nếu không có chương
                    parts = re.split(r'\n\s*\n', text)
                    if len(parts) <= 1:
                         self.show_error("Không tìm thấy định dạng chương (第X章/Chương X/Chapter X) hoặc ngắt đoạn bằng dòng trống. Văn bản sẽ được xử lý như một phần duy nhất.")
                         return [text.strip()] # Trả về toàn bộ văn bản nếu không chia được
                    else:
                         # Tìm thấy ngắt đoạn, dùng chúng
                         result = [p.strip() for p in parts if p.strip()]
                         if not result:
                              self.show_error("Văn bản trống sau khi chia theo dòng trống.")
                              return None
                         self.queue.put((self.progress_text, "Cảnh báo: Không tìm thấy chương, chia theo dòng trống.", False))
                         return result

                # Ghép lại phần tiêu đề chương với nội dung của nó
                chapters = []
                current_chapter_content = ""
                if parts[0].strip(): # Phần text trước chương đầu tiên (nếu có)
                    current_chapter_content += parts[0].strip() + "\n\n" # Thêm vào phần đầu

                for i in range(1, len(parts), 2): # Bước nhảy 2 để lấy delimiter và nội dung sau nó
                    delimiter = parts[i].strip()
                    content = parts[i+1].strip()
                    # Bắt đầu chương mới
                    if current_chapter_content and delimiter: # Chỉ thêm nếu có nội dung chương trước đó
                         chapters.append(current_chapter_content.strip())

                    current_chapter_content = delimiter + "\n" + content # Bắt đầu chương mới với tiêu đề

                # Thêm chương cuối cùng
                if current_chapter_content.strip():
                    chapters.append(current_chapter_content.strip())

                if not chapters:
                     self.show_error("Không trích xuất được nội dung chương nào.")
                     return None

                print(f"Đã chia thành {len(chapters)} chương.")
                return chapters

            elif split_method == "Theo số ký tự":
                # Đã validate split_length ở đầu hàm
                if language == "ENG":
                    # Chia theo từ cho tiếng Anh
                    return self.smart_split_by_words(text, split_length)
                else: # Tiếng Trung, Việt hoặc khác - chia theo ký tự
                    result = []
                    start = 0
                    text_len = len(text)
                    while start < text_len:
                        end = start + split_length
                        # Cố gắng tìm dấu ngắt câu gần nhất lùi về trước để không cắt giữa câu
                        if end < text_len:
                            # Tìm dấu chấm, hỏi, than, xuống dòng gần nhất trong khoảng 100 ký tự cuối
                            split_pos = -1
                            search_start = max(start, end - 100)
                            possible_splits = [m.start() for m in re.finditer(r'[.!?\n\r]+', text[search_start:end])]
                            if possible_splits:
                                split_pos = search_start + max(possible_splits) + 1 # Vị trí ngay sau dấu ngắt
                            elif '\n' in text[start:end]:
                                split_pos = text.rfind('\n', start, end) + 1 # Tìm xuống dòng gần nhất
                            else:
                                # Nếu không có dấu ngắt câu/dòng, tìm khoảng trắng gần nhất
                                space_pos = text.rfind(' ', start, end)
                                if space_pos != -1:
                                    split_pos = space_pos + 1
                                else:
                                     split_pos = end # Cắt cứng nếu không tìm được chỗ phù hợp

                            if split_pos > start : # Đảm bảo có tiến triển
                                end = split_pos

                        chunk = text[start:end].strip()
                        if chunk: # Chỉ thêm nếu chunk không rỗng
                            result.append(chunk)
                        start = end

                    if not result:
                        self.show_error("Không thể chia văn bản theo số ký tự (kết quả rỗng).")
                        return None
                    print(f"Đã chia thành {len(result)} phần theo ký tự.")
                    return result

            else:
                raise ValueError("Phương thức chia văn bản không hợp lệ")
        except Exception as e:
            import traceback
            self.show_error(f"Lỗi nghiêm trọng khi chia văn bản: {str(e)}\n{traceback.format_exc()}")
            return None # Trả về None khi có lỗi nghiêm trọng

    def smart_split_by_words(self, text, max_words):
        """
        Splits text into chunks based on word count, respecting sentence boundaries.
        """
        # Cải thiện việc tách câu, hỗ trợ nhiều dấu câu hơn
        sentences = re.split(r'(?<=[.!?…])\s+', text.replace('\n', ' ')) # Thay newline bằng space để split câu tốt hơn
        chunks = []
        current_chunk_sentences = []
        current_word_count = 0

        for sentence in sentences:
            if not sentence.strip(): continue # Bỏ qua câu rỗng

            words_in_sentence = len(sentence.split())

            # Nếu một câu đã quá dài, chia nhỏ câu đó (trường hợp hiếm)
            if words_in_sentence > max_words:
                 print(f"Cảnh báo: Câu quá dài ({words_in_sentence} từ), sẽ bị chia nhỏ.")
                 words = sentence.split()
                 for i in range(0, len(words), max_words):
                     sub_sentence = ' '.join(words[i:i+max_words])
                     if sub_sentence:
                         chunks.append(sub_sentence)
                 # Đặt lại chunk hiện tại sau khi xử lý câu dài
                 current_chunk_sentences = []
                 current_word_count = 0
                 continue # Chuyển sang câu tiếp theo

            # Kiểm tra xem thêm câu này có vượt quá giới hạn không
            if current_word_count + words_in_sentence <= max_words:
                current_chunk_sentences.append(sentence)
                current_word_count += words_in_sentence
            else:
                # Đóng chunk hiện tại và bắt đầu chunk mới
                if current_chunk_sentences:
                    chunks.append(' '.join(current_chunk_sentences).strip())
                current_chunk_sentences = [sentence]
                current_word_count = words_in_sentence

        # Thêm chunk cuối cùng nếu còn
        if current_chunk_sentences:
            chunks.append(' '.join(current_chunk_sentences).strip())

        if not chunks:
             self.show_error("Không thể chia văn bản theo số từ (kết quả rỗng).")
             return None
        print(f"Đã chia thành {len(chunks)} phần theo từ.")
        return chunks

    def load_results(self):
        try:
            results_dir = os.path.join(os.path.expanduser("~"), "Downloads",
                                     "gemini_results")
            if not os.path.exists(results_dir):
                messagebox.showinfo("Thông tin", "Thư mục 'gemini_results' trong Downloads không tồn tại. Chưa có kết quả nào được lưu.")
                return

            files = [f for f in os.listdir(results_dir) if f.startswith("gemini_result_") and f.endswith(".txt")]
            if not files:
                 messagebox.showinfo("Thông tin", "Không tìm thấy file kết quả nào trong thư mục 'gemini_results'.")
                 return

            # Tìm file mới nhất dựa trên tên (timestamp) thay vì ctime
            # Điều này đáng tin cậy hơn nếu file bị copy/move
            files.sort(reverse=True) # Sắp xếp giảm dần theo tên (timestamp)
            latest_file = files[0]
            latest_file_path = os.path.join(results_dir, latest_file)

            with open(latest_file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Hiển thị nội dung file lên ô result_text thay vì completion_text
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, content)
            self.result_text.see("1.0") # Cuộn lên đầu
            self.completion_text.delete("1.0", tk.END)
            self.completion_text.insert(tk.END, f"Đã tải nội dung từ file:\n{latest_file_path}")

        except Exception as e:
            import traceback
            self.show_error(f"Lỗi khi tải kết quả: {str(e)}\n{traceback.format_exc()}")

# --- Cần import traceback ở đầu file ---
import traceback

def main():
    root = tk.Tk()
    app = GeminiInterface(root)
    root.mainloop()

if __name__ == "__main__":
    main()