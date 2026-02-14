import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import google.generativeai as genai
from openai import OpenAI
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
GOOGLE_FALLBACK_MODEL = "gemini-2.5-flash-lite"
API_TIMEOUT_SECONDS = 7 * 60 # 7 phút
DEFAULT_PROVIDER = "Google"
MEGALLM_BASE_URL = "https://ai.megallm.io/v1"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
POE_BASE_URL = "https://api.poe.com/v1"
MISTRAL_BASE_URL = "https://api.mistral.ai/v1"
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://localhost",
    "X-Title": "GeminiLocal"
}
GOOGLE_MODELS = [
    "gemini-2.0-flash-lite-preview-02-05",
    "gemini-2.5-pro-preview-05-06",
    "gemini-3-flash-preview",
    "gemini-2.5-pro-exp-03-25",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash-lite"
]
MEGALLM_MODELS = [
    "gpt-5.1",
    "gpt-5",
    "gpt-4o",
    "gpt-4.1",
    "claude-opus-4-1-20250805",
    "claude-sonnet-4-5-20250929",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-haiku-4-5-20251001",
    "gemini-2.5-pro",
    "gemini-3-pro-preview",
    "glm-4.6",
    "deepseek-ai/deepseek-v3.1",
    "deepseek-v3.2",
    "moonshotai/kimi-k2-thinking"
]
OPENROUTER_MODELS = [
    "deepseek/deepseek-r1:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "deepseek/deepseek-chat-v3.1:free",
    "tngtech/deepseek-r1t2-chimera:free",
    "tngtech/deepseek-r1t-chimera:free",
    "deepseek/deepseek-r1-0528:free",
    "x-ai/grok-4.1-fast",
    "x-ai/grok-4.1-fast:free",
    "alibaba/tongyi-deepresearch-30b-a3b:free",
    "meituan/longcat-flash-chat:free",
    "moonshotai/kimi-k2:free",
    "z-ai/glm-4.5-air:free",
    "qwen/qwen2.5-vl-72b-instruct:free",
    "qwen/qwen3-30b-a3b:free",
    "qwen/qwen3-235b-a22b:free",
    "google/gemini-2.0-flash-exp:free",
    "meta-llama/llama-3.3-70b-instruct:free"
]
# POE models
POE_MODELS = [
    "gemini-2.5-pro",
    "Gemini-2.5-Flash",
    "Gemini-2.5-Flash-Lite",
    "Gemini-3-Pro",
    "Grok-4",
    "Claude-Opus-4.1",
    "Claude-Haiku-4.5",
    "Claude-Opus-4.5",
    "Claude-Sonnet-4",
    "GPT-5.1",
    "GPT-5",
    "Deepseek-R1",
    "Deepseek-V3.2",
    "Deepseek-V3.2-Exp"
]
MISTRAL_MODELS = [
    "mistral-medium-latest",
    "mistral-small-latest",
    "mistral-large-latest",
    "mistral-large-2512",
    "mistral-small-2409"
]
PROVIDER_DEFAULT_MODELS = {
    "Google": "gemini-flash-latest",
    "MegaLLM": "gpt-5.1",
    "Open Router": "deepseek/deepseek-chat-v3.1:free",
    "POE": "gemini-2.5-pro",
    "Mistral": "mistral-small-2409"
}
PROVIDER_CONFIG = {
    "Google": {
        "models": GOOGLE_MODELS,
        "fallback_model": GOOGLE_FALLBACK_MODEL,
        "base_url": None
    },
    "MegaLLM": {
        "models": MEGALLM_MODELS,
        "fallback_model": None,
        "base_url": MEGALLM_BASE_URL
    },
    "Open Router": {
        "models": OPENROUTER_MODELS,
        "fallback_model": "tngtech/deepseek-r1t2-chimera:free",
        "base_url": OPENROUTER_BASE_URL,
        "headers": OPENROUTER_HEADERS
    },
    "POE": {
        "models": POE_MODELS,
        "fallback_model": "Gemini-2.5-Flash-Lite",
        "base_url": POE_BASE_URL
    },
    "Mistral": {
        "models": MISTRAL_MODELS,
        "fallback_model": None,
        "base_url": MISTRAL_BASE_URL
    }
}
# --- Kết thúc hằng số mới ---

class GeminiInterface:
    def __init__(self, root):
        self.root = root
        self.root.title("Gemini Pro v6 API Interface (with Retry)") # Cập nhật title
        self.root.geometry("800x900")

        self.root.option_add('*Font', ('Arial', 12))
        if os.name == 'nt':
            self.root.option_add('*Dialog.msg.font', ('Arial', 12))

        self.processing = False
        self.should_stop = False
        self.queue = queue.Queue()
        self.api_key = None  # Single API key (legacy)
        self.api_keys = []   # List of API keys for round robin
        self.api_key_index = 0  # Current index for round robin
        self.provider_var = tk.StringVar(value=DEFAULT_PROVIDER)

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

        # Language & provider selection (row layout, fixed width)
        lang_frame = ttk.LabelFrame(main_container, text="Chọn ngôn ngữ / Provider", padding="5")
        lang_frame.pack(fill="x", pady=5)
        lang_provider_frame = ttk.Frame(lang_frame)
        lang_provider_frame.pack(fill="x")
        self.language = ttk.Combobox(lang_provider_frame, values=["中文", "ENG", "Việt Nam"],
                                   font=('Arial', 12), state="readonly", width=10)
        self.language.set("中文")
        self.language.pack(side="left", padx=(0, 5))
        self.language.bind("<<ComboboxSelected>>", self.on_language_change)
        self.provider_combo = ttk.Combobox(
            lang_provider_frame,
            textvariable=self.provider_var,
            values=list(PROVIDER_CONFIG.keys()),
            font=('Arial', 12),
            state="readonly",
            width=12
        )
        self.provider_combo.pack(side="left", padx=(0, 5))
        self.provider_combo.bind("<<ComboboxSelected>>", self.on_provider_change)

        # Model selection (row layout, fixed width)
        model_frame = ttk.LabelFrame(main_container, text="Chọn model chính", padding="5")
        model_frame.pack(fill="x", pady=5)
        model_row = ttk.Frame(model_frame)
        model_row.pack(fill="x")
        self.model = ttk.Combobox(model_row, values=[], font=('Arial', 12), state="readonly", width=22)
        self.update_model_options(self.provider_var.get())
        self.model.pack(side="left", padx=(0, 5))

        # API Key Frame (row layout, fixed width)
        api_frame = ttk.LabelFrame(main_container, text="API Key", padding="5")
        api_frame.pack(fill="x", pady=5)
        api_row = ttk.Frame(api_frame)
        api_row.pack(fill="x")
        self.api_key_label = ttk.Label(api_row, text="Chưa có API Key nào được chọn", font=('Arial', 12), width=32, anchor="w")
        self.api_key_label.pack(side="left", padx=(0, 5))
        self.browse_api_key_button = ttk.Button(api_row, text="Chọn File API Key", command=self.browse_api_key_file, width=18)
        self.browse_api_key_button.pack(side="left")

        # Split method & length (row layout, fixed width)
        split_row = ttk.Frame(main_container)
        split_row.pack(fill="x", pady=5)
        split_frame = ttk.LabelFrame(split_row, text="Phương thức chia văn bản", padding="5")
        split_frame.pack(side="left", padx=(0, 5))
        self.split_method = ttk.Combobox(split_frame,
                    values=["Theo chương (第X章/Chương X)", "Theo số ký tự"],
                    font=('Arial', 12), width=20, state="readonly")
        self.split_method.set("Theo chương (第X章/Chương X)")
        self.split_method.pack()

        split_length_frame = ttk.LabelFrame(split_row, text="Số ký tự/số từ mỗi phần", padding="5")
        split_length_frame.pack(side="left")
        self.split_length_entry = ttk.Entry(split_length_frame, font=('Arial', 12), width=10)
        self.split_length_entry.pack()
        self.split_length_entry.insert(0, "10000")

        # Progress bar
        self.progress_bar = ttk.Progressbar(main_container, orient="horizontal",
                                          mode="determinate")
        self.progress_bar.pack(fill="x", pady=5)

        # Prompt input + context input
        prompt_context_frame = ttk.Frame(main_container)
        prompt_context_frame.pack(fill="x", pady=5)

        prompt_frame = ttk.LabelFrame(prompt_context_frame, text="Nhập prompt", padding="5")
        prompt_frame.pack(side="left", fill="both", expand=True)
        self.prompt_text = self.create_text_widget(prompt_frame, height=4)

        context_frame = ttk.LabelFrame(prompt_context_frame, text="Bối cảnh chương trước (tóm tắt)", padding="5")
        context_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.prev_summary_text = self.create_text_widget(context_frame, height=4)
        self.prev_summary_text.insert("1.0", "")

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
    def build_translation_prompt(self, chapter_text, prev_summary):
        prompt = self.prompt_text.get("1.0", tk.END).strip()
        context = prev_summary.strip()
        prompt_parts = [prompt]
        if context:
            prompt_parts.append(f"\nBối cảnh chương trước: {context}")
        prompt_parts.append("\nNội dung cần dịch:\n" + chapter_text)
        prompt_parts.append("\nYêu cầu:\n1. Trả về bản dịch tiếng Việt của chương trên, không dùng Markdown.\n2. Trả về tóm tắt nội dung chương vừa dịch, tối đa 350 từ, giữ nguyên đại từ nhân xưng được sử dụng trong văn bản dịch. Tuyệt đối không ghép đại từ trước tên riêng (ví dụ: chỉ viết 'Yến Dịch', không được viết 'anh Yến Dịch') Giữ đúng đại từ khi dẫn truyện. \nTrả kết quả theo đúng thứ tự:\n---DỊCH---\n[Bản dịch]\n---TÓM TẮT---\n[Tóm tắt chương]")
        return "\n".join(prompt_parts)

    def extract_translation_and_summary(self, response_text):
        import re
        parts = re.split(r'---DỊCH---|---TÓM TẮT---', response_text)
        if len(parts) >= 3:
            translation = parts[1].strip()
            summary = parts[2].strip()
        else:
            translation = response_text.strip()
            summary = ""
        return translation, summary

    def on_language_change(self, event):
        """Update label when language changes."""
        language = self.language.get()
        if language == "ENG":
            self.split_length_label.config(text="Số từ mỗi phần:")
        elif language in ["中文", "Việt Nam"]:
            self.split_length_label.config(text="Số ký tự mỗi phần:")
        else:
            self.split_length_label.config(text="Số ký tự/số từ mỗi phần:")

    def on_provider_change(self, event):
        """Refresh model list when provider changes."""
        self.update_model_options()

    def update_model_options(self, provider=None):
        """Update model combobox based on selected provider."""
        provider = provider or self.provider_var.get()
        config = PROVIDER_CONFIG.get(provider, {})
        models = config.get("models", [])
        self.model["values"] = models
        default_model = PROVIDER_DEFAULT_MODELS.get(provider)
        if default_model in models:
            self.model.set(default_model)
        elif models:
            self.model.set(models[0])
        else:
            self.model.set("")

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
                keys = []
                with open(file_path, 'r') as f:
                    for line in f:
                        stripped_line = line.strip()
                        if stripped_line and not stripped_line.startswith('#'):
                            keys.append(stripped_line)
                if not keys:
                    self.api_key_label.config(text="File API Key không chứa key hợp lệ")
                    self.api_key = None
                    self.api_keys = []
                else:
                    self.api_key = keys[0]
                    self.api_keys = keys
                    self.api_key_index = 0
                    self.api_key_label.config(text=f"Đã tải {len(keys)} API Key từ: {os.path.basename(file_path)}")
            except Exception as e:
                self.api_key_label.config(text=f"Lỗi đọc file API Key: {str(e)}")
                self.api_key = None
                self.api_keys = []

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
    def _call_model_api(self, provider, model_name, prompt_content, openai_client=None):
        """Hàm thực hiện gọi API theo provider được chọn."""
        try:
            if provider == "Google":
                model_instance = genai.GenerativeModel(model_name)
                response = model_instance.generate_content(prompt_content)
                if not response or not response.text:
                    return None, f"Không nhận được nội dung hợp lệ từ model {model_name}"
                return response.text, None
            elif provider in ["MegaLLM", "Open Router", "POE", "Mistral"]:
                if openai_client is None:
                    return None, f"{provider} client chưa được khởi tạo."
                response = openai_client.chat.completions.create(
                    model=model_name,
                    messages=[{"role": "user", "content": prompt_content}]
                )
                content = self._extract_megallm_content(response)
                if not content:
                    return None, f"Không nhận được nội dung hợp lệ từ model {model_name} ({provider})"
                return content, None
            else:
                return None, f"Provider {provider} chưa hỗ trợ."
        except Exception as e:
            error_msg = f"Lỗi API khi gọi provider {provider}, model {model_name}: {type(e).__name__} - {str(e)}"
            print(error_msg)
            return None, error_msg

    def _extract_megallm_content(self, response):
        """Trích nội dung text từ response theo định dạng OpenAI-compatible."""
        choices = getattr(response, "choices", None)
        if not choices:
            return None
        first_choice = choices[0]
        message = getattr(first_choice, "message", None)
        content = None
        if message is not None:
            content = getattr(message, "content", None)
            if isinstance(content, dict):
                content = content.get("content")
        if isinstance(content, list):
            parts = []
            for part in content:
                if isinstance(part, dict):
                    parts.append(part.get("text") or part.get("content") or "")
                else:
                    parts.append(str(part))
            content = " ".join(part for part in parts if part).strip()
        elif isinstance(content, str):
            content = content.strip()
        if not content and isinstance(message, dict):
            content = (message.get("content") or "").strip()
        if not content:
            text_attr = getattr(first_choice, "text", None)
            if isinstance(text_attr, str):
                content = text_attr.strip()
        return content

    # --- Hàm gọi API với Retry và Timeout ---
    def call_model_with_retry_and_timeout(self, provider, primary_model_name, prompt_content, openai_client=None):
        """Gọi API với timeout, retry bằng model fallback nếu cần."""
        start_time = time.time()
        error_message_final = "Không có lỗi"
        provider_config = PROVIDER_CONFIG.get(provider, {})
        fallback_model = provider_config.get("fallback_model")

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self._call_model_api, provider, primary_model_name, prompt_content, openai_client)
            try:
                print(f"Attempting primary model ({provider}): {primary_model_name}")
                result_text, error_message = future.result(timeout=API_TIMEOUT_SECONDS)
                if error_message:
                    print(f"Primary model failed: {error_message}")
                    error_message_final = error_message
                else:
                    print("Primary model success.")
                    return result_text, None
            except concurrent.futures.TimeoutError:
                elapsed = time.time() - start_time
                print(f"Primary model timeout after {elapsed:.2f}s")
                error_message_final = f"Model chính ({primary_model_name}) timeout sau {elapsed:.2f} giây."
            except Exception as e:
                elapsed = time.time() - start_time
                print(f"Primary model unexpected error after {elapsed:.2f}s: {e}")
                error_message_final = f"Lỗi không xác định với model chính ({primary_model_name}): {str(e)}"

        if not fallback_model:
            error_message_final += "\nProvider không có fallback model."
            return None, error_message_final

        print(f"Trying fallback model: {fallback_model}")
        self.queue.put((self.progress_text, f"\n-> Thử lại với model {fallback_model}...", False))

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            fallback_start_time = time.time()
            future = executor.submit(self._call_model_api, provider, fallback_model, prompt_content, openai_client)
            try:
                result_text, error_message = future.result(timeout=API_TIMEOUT_SECONDS)
                if error_message:
                    print(f"Fallback model failed: {error_message}")
                    error_message_final += f"\nRetry với {fallback_model} cũng thất bại: {error_message}"
                    return None, error_message_final
                else:
                    elapsed_fallback = time.time() - fallback_start_time
                    print(f"Fallback model success after {elapsed_fallback:.2f}s.")
                    self.queue.put((self.progress_text, f"\n-> Retry với {fallback_model} thành công.", False))
                    return result_text, None
            except concurrent.futures.TimeoutError:
                elapsed = time.time() - fallback_start_time
                print(f"Fallback model timeout after {elapsed:.2f}s")
                error_message_final += f"\nRetry với {fallback_model} cũng timeout sau {elapsed:.2f} giây."
                return None, error_message_final
            except Exception as e:
                elapsed = time.time() - fallback_start_time
                print(f"Fallback model unexpected error after {elapsed:.2f}s: {e}")
                error_message_final += f"\nLỗi không xác định khi retry với {fallback_model}: {str(e)}"
                return None, error_message_final
    def _process_request_thread(self):
        import traceback
        try:
            provider = self.provider_var.get()
            provider_config = PROVIDER_CONFIG.get(provider)
            if not provider_config:
                self.show_error(f"Provider {provider} chưa được cấu hình.")
                self.processing = False
                self.root.after(0, lambda: self.submit_button.configure(state='normal'))
                self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
                return
            openai_client = None
            # Round robin API key setup
            api_keys = self.api_keys if self.api_keys else ([self.api_key] if self.api_key else [])
            api_key_count = len(api_keys)
            api_key_index = self.api_key_index if api_key_count > 0 else 0
            if provider == "Google":
                genai.configure(api_key=api_keys[api_key_index] if api_key_count > 0 else None)
            elif provider in ["MegaLLM", "Open Router", "POE", "Mistral"]:
                try:
                    base_url = provider_config.get("base_url")
                    if not base_url and provider == "MegaLLM":
                        base_url = MEGALLM_BASE_URL
                    default_headers = provider_config.get("headers")
                    openai_client = OpenAI(
                        base_url=base_url,
                        api_key=api_keys[api_key_index] if api_key_count > 0 else None,
                        default_headers=default_headers
                    )
                except Exception as client_error:
                    self.show_error(f"Không thể khởi tạo {provider} client: {client_error}")
                    self.processing = False
                    self.root.after(0, lambda: self.submit_button.configure(state='normal'))
                    self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
                    return
            else:
                self.show_error(f"Provider {provider} chưa hỗ trợ.")
                self.processing = False
                self.root.after(0, lambda: self.submit_button.configure(state='normal'))
                self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
                return
            primary_model_name = self.model.get()

            text = self.additional_text.get("1.0", tk.END).strip()
            split_method = self.split_method.get()
            split_length = self.split_length_entry.get()
            if split_method == "Theo chương (第X章/Chương X)":
                chapters = self.split_text(text)
            else:  # "Theo số ký tự"
                chapters = self.split_text(text)
            if not chapters:
                self.show_error("Không thể chia văn bản thành các phần.")
                self.processing = False
                self.root.after(0, lambda: self.submit_button.configure(state='normal'))
                self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
                return

            results_dir = os.path.join(os.path.expanduser("~"), "Downloads", "gemini_results")
            os.makedirs(results_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
            result_file = os.path.join(results_dir, f"gemini_result_{timestamp}_{primary_model_name.replace('/', '-').replace(':', '_')}.txt")

            self.progress_bar["maximum"] = len(chapters)
            self.progress_bar["value"] = 0

            status_messages = []
            total_parts = len(chapters)
            prev_summary = self.prev_summary_text.get("1.0", tk.END).strip()

            translations_only = []
            for i, chapter in enumerate(chapters, 1):
                if self.should_stop:
                    status_messages.append(f"Phần {i}/{total_parts}: Đã dừng bởi người dùng.")
                    self.queue.put((self.completion_text,
                                    f"Xử lý đã bị dừng ở phần {i}.\n" + "\n".join(status_messages) + f"\nKết quả chưa hoàn chỉnh lưu tại: {result_file}", True))
                    break

                # Round robin API key selection
                if api_key_count > 0:
                    current_key = api_keys[api_key_index]
                    self.api_key_index = (api_key_index + 1) % api_key_count
                else:
                    current_key = None

                # Update client/key for each call
                if provider == "Google":
                    genai.configure(api_key=current_key)
                elif provider in ["MegaLLM", "Open Router", "POE", "Mistral"]:
                    try:
                        base_url = provider_config.get("base_url")
                        if not base_url and provider == "MegaLLM":
                            base_url = MEGALLM_BASE_URL
                        default_headers = provider_config.get("headers")
                        openai_client = OpenAI(
                            base_url=base_url,
                            api_key=current_key,
                            default_headers=default_headers
                        )
                    except Exception as client_error:
                        self.show_error(f"Không thể khởi tạo {provider} client: {client_error}")
                        self.processing = False
                        self.root.after(0, lambda: self.submit_button.configure(state='normal'))
                        self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
                        return

                # Xây dựng prompt cho từng chương
                prompt_content = self.build_translation_prompt(chapter, prev_summary)

                # Hiển thị full prompt gửi API để debug, kèm thông tin key
                self.queue.put((self.progress_text,
                    f"Đang xử lý phần {i}/{total_parts}\n"
                    f"Model chính: {primary_model_name}\n"
                    f"Đang dùng API KEY thứ {api_key_index+1}/{api_key_count}\n"
                    f"Prompt gửi API:\n{'='*20}\n{prompt_content}\n{'='*20}", True))
                self.queue.put((self.result_text, f"--- Đang chờ kết quả phần {i} ---", True))

                response_text, error_msg = self.call_model_with_retry_and_timeout(
                    provider, primary_model_name, prompt_content, openai_client
                )

                if self.should_stop:
                    status_messages.append(f"Phần {i}/{total_parts}: Đã dừng bởi người dùng sau khi gọi API.")
                    self.queue.put((self.completion_text,
                                    f"Xử lý đã bị dừng ở phần {i}.\n" + "\n".join(status_messages) + f"\nKết quả chưa hoàn chỉnh lưu tại: {result_file}", True))
                    break

                if error_msg:
                    error_log = f"LỖI PHẦN {i}: {error_msg}"
                    print(error_log)
                    self.queue.put((self.result_text, error_log, True))
                    status_messages.append(f"Phần {i}/{total_parts}: Thất bại - {error_msg.splitlines()[0]}")
                    try:
                        with open(result_file, 'a', encoding='utf-8') as f:
                            f.write(f"## LỖI PHẦN {i} ##\n")
                            f.write(f"{error_msg}\n\n")
                    except Exception as write_err:
                        print(f"Không thể ghi lỗi vào file: {write_err}")
                        status_messages[-1] += " (Không ghi được file)"
                    self.progress_bar["value"] = i
                    self.queue.put((self.completion_text, "\n".join(status_messages) + f"\nKết quả đang lưu tại: {result_file}", True))
                    continue

                # Tách bản dịch và tóm tắt
                translation, summary = self.extract_translation_and_summary(response_text)
                translations_only.append(translation)
                self.queue.put((self.result_text, f"Kết quả xử lý phần {i}:\n{translation}\n\n---TÓM TẮT---\n{summary}", True))
                status_messages.append(f"Phần {i}/{total_parts}: Hoàn thành.")
                # Ghi kết quả vào file
                try:
                    with open(result_file, 'a', encoding='utf-8') as f:
                        f.write(f"## ")
                        f.write(translation + "\n\n")
                        f.write(f"## TÓM TẮT PHẦN {i} ##\n")
                        f.write(summary + "\n\n")
                except Exception as write_err:
                    print(f"Không thể ghi kết quả phần {i} vào file: {write_err}")
                    status_messages[-1] = f"Phần {i}/{total_parts}: Hoàn thành (Lỗi ghi file)"
                self.progress_bar["value"] = i
                self.queue.put((self.completion_text, "\n".join(status_messages) + f"\nKết quả đang lưu tại: {result_file}", True))
                # Cập nhật tóm tắt cho chương sau
                prev_summary = summary
                self.prev_summary_text.delete("1.0", tk.END)
                self.prev_summary_text.insert("1.0", summary)

                # Advance round robin index for next call
                api_key_index = self.api_key_index

            # Sau khi hoàn thành, lưu file tổng hợp chỉ bản dịch
            result_file_no_summary = result_file.replace('.txt', '_no_summary.txt')
            try:
                with open(result_file_no_summary, 'w', encoding='utf-8') as f:
                    for idx, translation in enumerate(translations_only, 1):
                        f.write(f"## ")
                        f.write(translation + "\n\n")
            except Exception as write_err:
                print(f"Không thể ghi file tổng hợp không tóm tắt: {write_err}")

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
            error_traceback = traceback.format_exc()
            print(f"Lỗi nghiêm trọng trong _process_request_thread: {error_traceback}")
            self.show_error(f"Lỗi không xác định trong quá trình xử lý: {str(e)}")
            self.queue.put((self.completion_text, f"Đã xảy ra lỗi nghiêm trọng: {str(e)}", True))
        finally:
            self.processing = False
            self.root.after(0, lambda: self.submit_button.configure(state='normal'))
            self.root.after(0, lambda: self.stop_button.configure(state='disabled'))
            print("Processing thread finished.")

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
                        end = min(start + split_length, text_len)  # Không vượt quá độ dài văn bản
                        
                        # Cố gắng tìm dấu ngắt câu gần nhất lùi về trước để không cắt giữa câu
                        if end < text_len:
                            split_pos = end  # Mặc định cắt tại vị trí end
                            
                            # Tìm dấu chấm, hỏi, than, xuống dòng gần nhất trong khoảng
                            search_start = max(start, end - 100)
                            possible_splits = [m.end() for m in re.finditer(r'[。!?！？\n\r]', text[search_start:end])]
                            if possible_splits:
                                # Lấy vị trí ngay sau dấu ngắt gần nhất
                                split_pos = search_start + max(possible_splits)
                            else:
                                # Nếu không có dấu ngắt câu, tìm khoảng trắng gần nhất
                                space_pos = text.rfind(' ', start, end)
                                if space_pos > start:  # Đảm bảo tìm được và vị trí hợp lệ
                                    split_pos = space_pos + 1
                                # Nếu không tìm được gì, giữ nguyên end (cắt cứng)
                            
                            if split_pos > start:  # Đảm bảo có tiến triển
                                end = split_pos

                        chunk = text[start:end].strip()
                        if chunk:  # Chỉ thêm nếu chunk không rỗng
                            result.append(chunk)
                        
                        # Đảm bảo tiến triển: nếu end == start, tăng thêm 1 để tránh vòng lặp vô hạn
                        if end <= start:
                            start += 1
                        else:
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
