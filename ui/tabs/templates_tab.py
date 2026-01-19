"""
Templates Tab for OCRMill - TariffMill Style

Combines template management and AI assistant into a single tab interface.
Replaces the separate template menus and dialogs.
"""

import json
import logging
import os
import sys
import re
import shutil
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QStackedWidget,
    QTextEdit, QPlainTextEdit, QComboBox, QLineEdit, QFormLayout,
    QGroupBox, QFileDialog, QMessageBox, QScrollArea, QFrame,
    QProgressBar, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.theme_manager import get_theme_manager

logger = logging.getLogger(__name__)


class PythonHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Python code in the template editor."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme_manager = get_theme_manager()
        self._setup_highlighting_rules()

    def _setup_highlighting_rules(self):
        """Set up Python syntax highlighting rules."""
        self.highlighting_rules = []

        is_dark = self.theme_manager.is_dark_theme()

        # Keyword format
        keyword_format = QTextCharFormat()
        keyword_format.setForeground(QColor("#c586c0" if is_dark else "#af00db"))
        keyword_format.setFontWeight(QFont.Weight.Bold)
        keywords = [
            'and', 'as', 'assert', 'async', 'await', 'break', 'class', 'continue',
            'def', 'del', 'elif', 'else', 'except', 'False', 'finally', 'for',
            'from', 'global', 'if', 'import', 'in', 'is', 'lambda', 'None',
            'nonlocal', 'not', 'or', 'pass', 'raise', 'return', 'True', 'try',
            'while', 'with', 'yield'
        ]
        for word in keywords:
            pattern = fr'\b{word}\b'
            self.highlighting_rules.append((pattern, keyword_format))

        # String format
        string_format = QTextCharFormat()
        string_format.setForeground(QColor("#ce9178" if is_dark else "#a31515"))
        self.highlighting_rules.append((r'"[^"\\]*(\\.[^"\\]*)*"', string_format))
        self.highlighting_rules.append((r"'[^'\\]*(\\.[^'\\]*)*'", string_format))

        # Comment format
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#6a9955" if is_dark else "#008000"))
        self.highlighting_rules.append((r'#[^\n]*', comment_format))

        # Function/method format
        function_format = QTextCharFormat()
        function_format.setForeground(QColor("#dcdcaa" if is_dark else "#795e26"))
        self.highlighting_rules.append((r'\bdef\s+(\w+)', function_format))

        # Class format
        class_format = QTextCharFormat()
        class_format.setForeground(QColor("#4ec9b0" if is_dark else "#267f99"))
        self.highlighting_rules.append((r'\bclass\s+(\w+)', class_format))

        # Number format
        number_format = QTextCharFormat()
        number_format.setForeground(QColor("#b5cea8" if is_dark else "#098658"))
        self.highlighting_rules.append((r'\b[0-9]+\.?[0-9]*\b', number_format))

        # self format
        self_format = QTextCharFormat()
        self_format.setForeground(QColor("#9cdcfe" if is_dark else "#0000ff"))
        self.highlighting_rules.append((r'\bself\b', self_format))

    def highlightBlock(self, text):
        """Apply syntax highlighting to a block of text."""
        for pattern, format in self.highlighting_rules:
            import re as regex
            for match in regex.finditer(pattern, text):
                start = match.start()
                length = match.end() - match.start()
                self.setFormat(start, length, format)


class AITemplateChatThread(QThread):
    """Background thread for AI chat interactions with template assistant."""
    finished = pyqtSignal(str)  # AI response text
    error = pyqtSignal(str)
    stream_update = pyqtSignal(str)  # For streaming responses

    def __init__(self, provider: str, model: str, api_key: str,
                 current_code: str, user_message: str, conversation_history: list,
                 invoice_text: str = ""):
        super().__init__()
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.current_code = current_code
        self.user_message = user_message
        self.conversation_history = conversation_history
        self.invoice_text = invoice_text
        self._cancelled = False

    def cancel(self):
        """Cancel the current request."""
        self._cancelled = True

    def run(self):
        """Run the AI request in background."""
        try:
            # Build system prompt with current template context
            system_prompt = self._build_system_prompt()

            # Build messages list
            messages = []
            for msg in self.conversation_history:
                messages.append(msg)
            messages.append({"role": "user", "content": self.user_message})

            # Call appropriate provider
            if self.provider == "Anthropic":
                result = self._call_anthropic(system_prompt, messages)
            elif self.provider == "OpenAI":
                result = self._call_openai(system_prompt, messages)
            elif self.provider == "Google Gemini":
                result = self._call_gemini(system_prompt, messages)
            elif self.provider == "Groq":
                result = self._call_groq(system_prompt, messages)
            elif self.provider == "Ollama":
                result = self._call_ollama(system_prompt, messages)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            if not self._cancelled:
                self.finished.emit(result)

        except Exception as e:
            if not self._cancelled:
                logger.error(f"AI chat error: {e}")
                self.error.emit(str(e))

    def _build_system_prompt(self) -> str:
        """Build the system prompt with template context."""
        invoice_context = ""
        if self.invoice_text:
            invoice_context = f"\n\n## Sample Invoice Text\n```\n{self.invoice_text[:4000]}\n```"

        return f"""You are an expert Python developer and AI assistant for OCRMill, an invoice OCR processing application.

## Application Context

**OCRMill** is an invoice OCR processing application that:
- Extracts data from PDF invoices using AI-powered OCR
- Uses customizable Python templates to parse different invoice formats
- Maps extracted fields (part numbers, quantities, values, descriptions)
- Templates inherit from BaseTemplate class with extract() method

## Current Template Code
```python
{self.current_code}
```
{invoice_context}

## Guidelines
When helping with templates:
1. Preserve the overall structure (class name, imports, base class)
2. Only modify the specific parts the user asks about
3. Return the COMPLETE modified template code wrapped in ```python ... ``` markers
4. Explain what you changed after the code block
5. Use regex patterns appropriate for the invoice format
6. Handle edge cases and missing data gracefully

If the user asks a question, answer it clearly and provide modified code if applicable.

IMPORTANT: When providing code changes, always wrap the COMPLETE template code in:
```python
# your complete template code here
```"""

    def _call_anthropic(self, system_prompt: str, messages: list) -> str:
        """Call Anthropic Claude API."""
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        # Convert messages format
        api_messages = []
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        data = {
            "model": self.model,
            "max_tokens": 8192,
            "system": system_prompt,
            "messages": api_messages
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('content', [{}])[0].get('text', '')

    def _call_openai(self, system_prompt: str, messages: list) -> str:
        """Call OpenAI API."""
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        # Build messages with system prompt
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        data = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": api_messages
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('choices', [{}])[0].get('message', {}).get('content', '')

    def _call_gemini(self, system_prompt: str, messages: list) -> str:
        """Call Google Gemini API."""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {
            "Content-Type": "application/json"
        }

        # Build contents array
        contents = []
        # Add system instruction as first user turn
        combined_first = system_prompt
        if messages:
            combined_first += f"\n\nUser: {messages[0]['content']}"
            contents.append({
                "role": "user",
                "parts": [{"text": combined_first}]
            })
            for msg in messages[1:]:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({
                    "role": role,
                    "parts": [{"text": msg["content"]}]
                })
        else:
            contents.append({
                "role": "user",
                "parts": [{"text": combined_first}]
            })

        data = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": 8192
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            candidates = result.get('candidates', [])
            if candidates:
                return candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            return ''

    def _call_groq(self, system_prompt: str, messages: list) -> str:
        """Call Groq API (OpenAI-compatible)."""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        data = {
            "model": self.model,
            "max_tokens": 8192,
            "messages": api_messages
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=120) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('choices', [{}])[0].get('message', {}).get('content', '')

    def _call_ollama(self, system_prompt: str, messages: list) -> str:
        """Call local Ollama API."""
        url = "http://localhost:11434/api/chat"
        headers = {
            "Content-Type": "application/json"
        }

        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        data = {
            "model": self.model,
            "messages": api_messages,
            "stream": False
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result.get('message', {}).get('content', '')
        except urllib.error.URLError as e:
            if "Connection refused" in str(e) or "No connection" in str(e):
                raise ConnectionError(
                    f"Ollama is not running. Please start Ollama first:\n"
                    f"  1. Install Ollama from https://ollama.ai\n"
                    f"  2. Run 'ollama serve' in a terminal\n"
                    f"  3. Run 'ollama pull {self.model}' to download the model"
                )
            raise
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise ConnectionError(
                    f"Ollama model '{self.model}' not found.\n"
                    f"Please install it by running: ollama pull {self.model}\n\n"
                    f"Or make sure Ollama is running: ollama serve"
                )
            raise


class TemplatesTab(QWidget):
    """
    Templates management tab with AI assistant integration.
    TariffMill-style layout with template list on left, editor/AI on right.
    """

    template_created = pyqtSignal(str, str)  # name, file_path
    templates_changed = pyqtSignal()

    def __init__(self, config, db, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db
        self.theme_manager = get_theme_manager()
        self.templates_data = []
        self.current_template_path = None
        self.current_template_modified = False

        # AI chat state
        self.conversation_history = []
        self.chat_thread = None
        self.pending_code = None
        self.invoice_text = ""  # Sample invoice text for AI context

        self._setup_ui()
        self._apply_theme_styling()
        self._load_templates()

    def _setup_ui(self):
        """Set up the tab UI with splitter layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main splitter - left panel (templates list) and right panel (editor)
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left panel - Template list
        left_panel = self._create_template_list_panel()
        self.main_splitter.addWidget(left_panel)

        # Right panel - Stacked widget for editor and create modes
        self.right_stack = QStackedWidget()

        # Mode 0: Template Editor with AI Chat
        editor_widget = self._create_editor_panel()
        self.right_stack.addWidget(editor_widget)

        # Mode 1: Create New Template
        create_widget = self._create_new_template_panel()
        self.right_stack.addWidget(create_widget)

        # Mode 2: Welcome/Empty state
        welcome_widget = self._create_welcome_panel()
        self.right_stack.addWidget(welcome_widget)

        self.main_splitter.addWidget(self.right_stack)

        # Set splitter sizes (20% left, 80% right)
        self.main_splitter.setSizes([200, 800])

        layout.addWidget(self.main_splitter)

        # Start with welcome panel
        self.right_stack.setCurrentIndex(2)

    def _create_template_list_panel(self) -> QWidget:
        """Create the left panel with template list and action buttons."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header
        header = QLabel("Templates")
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        layout.addWidget(header)

        # Template list
        self.template_list = QListWidget()
        self.template_list.setAlternatingRowColors(True)
        self.template_list.itemClicked.connect(self._on_template_selected)
        self.template_list.itemDoubleClicked.connect(self._on_template_double_clicked)
        layout.addWidget(self.template_list, 1)

        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self.new_btn = QPushButton("New")
        self.new_btn.setToolTip("Create a new template with AI assistance")
        self.new_btn.clicked.connect(self._on_new_template)
        btn_layout.addWidget(self.new_btn)

        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.setToolTip("Duplicate selected template")
        self.duplicate_btn.clicked.connect(self._on_duplicate_template)
        self.duplicate_btn.setEnabled(False)
        btn_layout.addWidget(self.duplicate_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.setToolTip("Delete selected template")
        self.delete_btn.clicked.connect(self._on_delete_template)
        self.delete_btn.setEnabled(False)
        btn_layout.addWidget(self.delete_btn)

        layout.addLayout(btn_layout)

        # Refresh button
        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._load_templates)
        layout.addWidget(refresh_btn)

        # Test button
        self.test_btn = QPushButton("▶ Test Template")
        self.test_btn.setToolTip("Test the selected template")
        self.test_btn.clicked.connect(self._on_test_template)
        self.test_btn.setEnabled(False)
        layout.addWidget(self.test_btn)

        return panel

    def _create_editor_panel(self) -> QWidget:
        """Create the template editor panel with AI chat."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Header with template name and AI provider
        header_layout = QHBoxLayout()

        self.template_name_label = QLabel("Select a template")
        self.template_name_label.setStyleSheet("font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(self.template_name_label)

        header_layout.addStretch()

        # AI Provider selection
        header_layout.addWidget(QLabel("AI:"))
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItems(["Anthropic", "OpenAI", "Google Gemini", "Groq", "Ollama"])
        self.ai_provider_combo.setFixedWidth(120)
        header_layout.addWidget(self.ai_provider_combo)

        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"])
        self.ai_model_combo.setFixedWidth(200)
        self.ai_provider_combo.currentTextChanged.connect(self._on_provider_changed)
        header_layout.addWidget(self.ai_model_combo)

        layout.addLayout(header_layout)

        # Splitter for code editor and AI chat
        editor_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Code editor
        editor_container = QWidget()
        editor_layout = QVBoxLayout(editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)

        # Validation indicator
        self.validation_label = QLabel("✓ Valid")
        self.validation_label.setStyleSheet("color: #4ec9b0; font-size: 10pt;")
        editor_layout.addWidget(self.validation_label)

        self.code_editor = QPlainTextEdit()
        self.code_editor.setFont(QFont("Consolas", 10))
        self.code_editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.code_editor.textChanged.connect(self._on_code_changed)
        self.highlighter = PythonHighlighter(self.code_editor.document())
        editor_layout.addWidget(self.code_editor)

        editor_splitter.addWidget(editor_container)

        # Right: AI Chat
        chat_container = self._create_ai_chat_panel()
        editor_splitter.addWidget(chat_container)

        editor_splitter.setSizes([600, 400])
        layout.addWidget(editor_splitter, 1)

        # Bottom action buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.save_btn = QPushButton("Save Template")
        self.save_btn.clicked.connect(self._on_save_template)
        self.save_btn.setEnabled(False)
        action_layout.addWidget(self.save_btn)

        layout.addLayout(action_layout)

        return panel

    def _create_ai_chat_panel(self) -> QWidget:
        """Create the AI chat panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Header
        header = QLabel("🤖 AI Template Assistant")
        header.setStyleSheet("font-size: 12pt; font-weight: bold; color: #f0b429;")
        layout.addWidget(header)

        # Info text
        info_label = QLabel(
            "Select a template to edit, or create a new one.\n\n"
            "I can help you:\n"
            "• Fix regex patterns\n"
            "• Add new extraction fields\n"
            "• Handle new invoice formats\n"
            "• Explain template logic"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #888;")
        layout.addWidget(info_label)

        # Chat display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setPlaceholderText("Chat with AI about this template...")
        layout.addWidget(self.chat_display, 1)

        # Context label
        self.context_label = QLabel("⚡ No template selected")
        self.context_label.setStyleSheet("color: #888; font-size: 9pt;")
        layout.addWidget(self.context_label)

        # Invoice context button
        invoice_btn_layout = QHBoxLayout()
        self.load_invoice_btn = QPushButton("📄 Load Invoice")
        self.load_invoice_btn.setToolTip("Load a sample invoice PDF to provide context for the AI")
        self.load_invoice_btn.clicked.connect(self._on_load_invoice_context)
        invoice_btn_layout.addWidget(self.load_invoice_btn)

        self.invoice_status_label = QLabel("No invoice loaded")
        self.invoice_status_label.setStyleSheet("color: #888; font-size: 9pt;")
        invoice_btn_layout.addWidget(self.invoice_status_label)
        invoice_btn_layout.addStretch()
        layout.addLayout(invoice_btn_layout)

        # Message input
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Ask the AI to modify the template... (Enter to send)")
        self.chat_input.returnPressed.connect(self._on_send_message)
        layout.addWidget(self.chat_input)

        # Chat buttons
        chat_btn_layout = QHBoxLayout()

        self.send_btn = QPushButton("Send")
        self.send_btn.clicked.connect(self._on_send_message)
        chat_btn_layout.addWidget(self.send_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._on_cancel_chat)
        chat_btn_layout.addWidget(self.cancel_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self._on_clear_chat)
        chat_btn_layout.addWidget(self.clear_btn)

        chat_btn_layout.addStretch()

        self.apply_code_btn = QPushButton("Apply Code")
        self.apply_code_btn.setToolTip("Apply AI-suggested code to the editor")
        self.apply_code_btn.setEnabled(False)
        self.apply_code_btn.clicked.connect(self._on_apply_code)
        chat_btn_layout.addWidget(self.apply_code_btn)

        layout.addLayout(chat_btn_layout)

        return panel

    def _create_new_template_panel(self) -> QWidget:
        """Create the panel for creating new templates."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Header
        header = QLabel("Create New Template")
        header.setStyleSheet("font-size: 16pt; font-weight: bold;")
        layout.addWidget(header)

        # Sample Invoice section
        sample_group = QGroupBox("Sample Invoice")
        sample_layout = QVBoxLayout(sample_group)

        sample_info = QLabel(
            "Provide a sample invoice PDF or paste the text content.\n"
            "The AI will analyze it and generate a template."
        )
        sample_info.setWordWrap(True)
        sample_layout.addWidget(sample_info)

        # File browser
        file_layout = QHBoxLayout()
        self.sample_file_edit = QLineEdit()
        self.sample_file_edit.setPlaceholderText("Select a PDF file or paste text below...")
        self.sample_file_edit.setReadOnly(True)
        file_layout.addWidget(self.sample_file_edit)

        browse_btn = QPushButton("Browse PDF...")
        browse_btn.clicked.connect(self._on_browse_sample_pdf)
        file_layout.addWidget(browse_btn)
        sample_layout.addLayout(file_layout)

        # Text paste area
        self.sample_text_edit = QPlainTextEdit()
        self.sample_text_edit.setPlaceholderText("Or paste invoice text here...")
        self.sample_text_edit.setMaximumHeight(150)
        sample_layout.addWidget(self.sample_text_edit)

        layout.addWidget(sample_group)

        # Template settings
        settings_group = QGroupBox("Template Settings")
        settings_layout = QFormLayout(settings_group)

        self.new_template_name = QLineEdit()
        self.new_template_name.setPlaceholderText("e.g., acme_corp_invoice")
        settings_layout.addRow("Template Name:", self.new_template_name)

        self.new_supplier_name = QLineEdit()
        self.new_supplier_name.setPlaceholderText("e.g., Acme Corporation")
        settings_layout.addRow("Supplier Name:", self.new_supplier_name)

        self.new_client_name = QLineEdit()
        self.new_client_name.setPlaceholderText("e.g., My Company")
        settings_layout.addRow("Client:", self.new_client_name)

        self.new_country = QLineEdit()
        self.new_country.setPlaceholderText("e.g., US, CN, DE")
        settings_layout.addRow("Country of Origin:", self.new_country)

        layout.addWidget(settings_group)

        # Progress bar
        self.generate_progress = QProgressBar()
        self.generate_progress.setRange(0, 0)  # Indeterminate
        self.generate_progress.setVisible(False)
        layout.addWidget(self.generate_progress)

        # Generated template preview
        self.generated_preview = QPlainTextEdit()
        self.generated_preview.setReadOnly(True)
        self.generated_preview.setPlaceholderText("Generated template code will appear here...")
        self.generated_preview.setFont(QFont("Consolas", 9))
        self.generated_preview.setVisible(False)
        layout.addWidget(self.generated_preview, 1)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.generate_btn = QPushButton("Generate Template")
        self.generate_btn.clicked.connect(self._on_generate_template)
        btn_layout.addWidget(self.generate_btn)

        self.cancel_generate_btn = QPushButton("Cancel")
        self.cancel_generate_btn.setEnabled(False)
        btn_layout.addWidget(self.cancel_generate_btn)

        btn_layout.addStretch()

        self.save_new_btn = QPushButton("Save Template")
        self.save_new_btn.setEnabled(False)
        self.save_new_btn.clicked.connect(self._on_save_new_template)
        btn_layout.addWidget(self.save_new_btn)

        self.back_btn = QPushButton("Back to Templates")
        self.back_btn.clicked.connect(self._on_back_to_list)
        btn_layout.addWidget(self.back_btn)

        layout.addLayout(btn_layout)

        return panel

    def _create_welcome_panel(self) -> QWidget:
        """Create the welcome/empty state panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(40, 40, 40, 40)

        layout.addStretch()

        # Icon/title
        title = QLabel("🎨 Template Manager")
        title.setStyleSheet("font-size: 24pt; font-weight: bold; color: #5f9ea0;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Instructions
        info = QLabel(
            "Select a template from the list to edit it,\n"
            "or click 'New' to create a template with AI assistance.\n\n"
            "Templates define how OCRMill extracts data from invoices.\n"
            "Each template is tailored for a specific supplier format."
        )
        info.setStyleSheet("font-size: 11pt; color: #666;")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)

        layout.addSpacing(30)

        # Quick actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        new_btn = QPushButton("✨ Create New Template")
        new_btn.setMinimumWidth(200)
        new_btn.clicked.connect(self._on_new_template)
        btn_layout.addWidget(new_btn)

        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        layout.addStretch()

        return panel

    def _apply_theme_styling(self):
        """Apply theme-aware styling to the tab."""
        is_dark = self.theme_manager.is_dark_theme()

        if is_dark:
            self.template_list.setStyleSheet("""
                QListWidget {
                    background-color: #252526;
                    color: #cccccc;
                    border: 1px solid #3c3c3c;
                }
                QListWidget::item {
                    padding: 8px;
                    border-bottom: 1px solid #3c3c3c;
                }
                QListWidget::item:selected {
                    background-color: #094771;
                    color: white;
                }
                QListWidget::item:hover:!selected {
                    background-color: #2a2d2e;
                }
            """)

            self.code_editor.setStyleSheet("""
                QPlainTextEdit {
                    background-color: #1e1e1e;
                    color: #d4d4d4;
                    border: 1px solid #3c3c3c;
                    selection-background-color: #264f78;
                }
            """)
        else:
            self.template_list.setStyleSheet("""
                QListWidget {
                    background-color: #ffffff;
                    border: 1px solid #d0d0d0;
                }
                QListWidget::item {
                    padding: 8px;
                    border-bottom: 1px solid #e8e8e8;
                }
                QListWidget::item:selected {
                    background-color: #5f9ea0;
                    color: white;
                }
                QListWidget::item:hover:!selected {
                    background-color: #f0f8f8;
                }
            """)

    def _load_templates(self):
        """Load all templates from local and shared folders."""
        self.template_list.clear()
        self.templates_data = []

        # Local templates folder
        local_path = Path(__file__).parent.parent.parent / "templates"
        exclude_files = {'__init__.py', 'base_template.py', 'sample_template.py'}

        if local_path.exists():
            for f in sorted(local_path.glob("*.py")):
                if f.name not in exclude_files:
                    info = self._extract_template_info(f)
                    info['is_shared'] = False
                    self.templates_data.append(info)

        # Shared templates folder
        shared_folder = self.config.shared_templates_folder
        if shared_folder and Path(shared_folder).exists():
            shared_path = Path(shared_folder)
            for f in sorted(shared_path.glob("*.py")):
                if f.name not in exclude_files:
                    info = self._extract_template_info(f)
                    info['is_shared'] = True
                    # Check if it already exists in local (shared overrides)
                    existing = next((t for t in self.templates_data if t['file_name'] == info['file_name']), None)
                    if existing:
                        self.templates_data.remove(existing)
                    self.templates_data.append(info)

        # Populate list
        for template in self.templates_data:
            display_name = template.get('name', template['file_name'])
            item = QListWidgetItem(display_name)

            # Set tooltip
            tooltip = f"Supplier: {template.get('supplier', 'Unknown')}\n"
            tooltip += f"Client: {template.get('client', 'Unknown')}\n"
            tooltip += f"Country: {template.get('country', 'Unknown')}\n"
            tooltip += f"Path: {template['file_path']}"
            if template['is_shared']:
                tooltip += "\n(Shared)"
            item.setToolTip(tooltip)

            # Mark shared templates with color
            if template['is_shared']:
                item.setForeground(QColor("#10B981"))  # Green

            self.template_list.addItem(item)

    def _extract_template_info(self, file_path: Path) -> Dict[str, Any]:
        """Extract template metadata from a template file."""
        info = {
            'file_path': str(file_path),
            'file_name': file_path.stem,
            'name': file_path.stem.replace('_', ' ').title(),
            'supplier': '',
            'client': '',
            'country': '',
        }

        try:
            content = file_path.read_text(encoding='utf-8')

            # Extract metadata using regex
            patterns = {
                'name': r'^\s*name\s*=\s*["\'](.+?)["\']',
                'supplier': r'^\s*supplier\s*=\s*["\'](.+?)["\']',
                'client': r'^\s*client\s*=\s*["\'](.+?)["\']',
                'country': r'^\s*country\s*=\s*["\'](.+?)["\']',
            }

            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.MULTILINE)
                if match:
                    info[key] = match.group(1)
        except Exception:
            pass

        return info

    def _on_template_selected(self, item: QListWidgetItem):
        """Handle template selection."""
        index = self.template_list.row(item)
        if 0 <= index < len(self.templates_data):
            template = self.templates_data[index]
            self._load_template_into_editor(template)

            # Enable buttons
            self.duplicate_btn.setEnabled(True)
            self.delete_btn.setEnabled(not template['is_shared'])
            self.test_btn.setEnabled(True)

    def _on_template_double_clicked(self, item: QListWidgetItem):
        """Handle template double-click to edit."""
        self._on_template_selected(item)

    def _load_template_into_editor(self, template: Dict[str, Any]):
        """Load a template into the editor panel."""
        try:
            content = Path(template['file_path']).read_text(encoding='utf-8')
            self.code_editor.setPlainText(content)
            self.template_name_label.setText(template.get('name', template['file_name']))
            self.current_template_path = template['file_path']
            self.current_template_modified = False

            self.context_label.setText(f"⚡ Editing: {template['file_name']}.py")
            self.save_btn.setEnabled(not template['is_shared'])

            # Switch to editor panel
            self.right_stack.setCurrentIndex(0)

            # Update highlighter for current theme
            self.highlighter._setup_highlighting_rules()
            self.highlighter.rehighlight()

            self._validate_code()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load template:\n{e}")

    def _on_code_changed(self):
        """Handle code editor changes."""
        self.current_template_modified = True
        self._validate_code()

    def _validate_code(self):
        """Validate the Python code in the editor."""
        code = self.code_editor.toPlainText()
        try:
            compile(code, '<template>', 'exec')
            self.validation_label.setText("✓ Valid")
            self.validation_label.setStyleSheet("color: #4ec9b0;")
            return True
        except SyntaxError as e:
            self.validation_label.setText(f"✗ Syntax Error: Line {e.lineno}")
            self.validation_label.setStyleSheet("color: #f14c4c;")
            return False

    def _on_save_template(self):
        """Save the current template."""
        if not self.current_template_path:
            return

        if not self._validate_code():
            reply = QMessageBox.question(
                self, "Invalid Code",
                "The code has syntax errors. Save anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            content = self.code_editor.toPlainText()
            Path(self.current_template_path).write_text(content, encoding='utf-8')
            self.current_template_modified = False
            self.templates_changed.emit()
            QMessageBox.information(self, "Saved", "Template saved successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save template:\n{e}")

    def _on_new_template(self):
        """Switch to new template creation panel."""
        self.right_stack.setCurrentIndex(1)

        # Clear fields
        self.sample_file_edit.clear()
        self.sample_text_edit.clear()
        self.new_template_name.clear()
        self.new_supplier_name.clear()
        self.new_client_name.clear()
        self.new_country.clear()
        self.generated_preview.clear()
        self.generated_preview.setVisible(False)
        self.save_new_btn.setEnabled(False)

    def _on_back_to_list(self):
        """Return to template list view."""
        if self.template_list.count() > 0:
            self.right_stack.setCurrentIndex(2)  # Welcome
        else:
            self.right_stack.setCurrentIndex(2)

    def _on_duplicate_template(self):
        """Duplicate the selected template."""
        current = self.template_list.currentItem()
        if not current:
            return

        index = self.template_list.row(current)
        template = self.templates_data[index]

        # Get new name
        base_name = template['file_name'] + "_copy"
        new_name, ok = QMessageBox.getText(
            self, "Duplicate Template",
            "Enter name for the new template:",
            QLineEdit.EchoMode.Normal,
            base_name
        ) if hasattr(QMessageBox, 'getText') else (base_name, True)

        if not ok or not new_name:
            return

        # Copy to local templates
        local_path = Path(__file__).parent.parent.parent / "templates"
        new_path = local_path / f"{new_name}.py"

        if new_path.exists():
            QMessageBox.warning(self, "Error", "A template with that name already exists.")
            return

        try:
            shutil.copy(template['file_path'], new_path)
            self._load_templates()
            self.templates_changed.emit()
            QMessageBox.information(self, "Success", f"Template duplicated as '{new_name}'")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to duplicate template:\n{e}")

    def _on_delete_template(self):
        """Delete the selected template."""
        current = self.template_list.currentItem()
        if not current:
            return

        index = self.template_list.row(current)
        template = self.templates_data[index]

        if template['is_shared']:
            QMessageBox.warning(self, "Cannot Delete", "Shared templates cannot be deleted.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete '{template['name']}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                Path(template['file_path']).unlink()
                self._load_templates()
                self.templates_changed.emit()
                self.right_stack.setCurrentIndex(2)  # Back to welcome
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete template:\n{e}")

    def _on_test_template(self):
        """Test the selected template with a PDF file."""
        current = self.template_list.currentItem()
        if not current:
            return

        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Select Test PDF", "", "PDF Files (*.pdf)"
        )

        if not pdf_path:
            return

        index = self.template_list.row(current)
        template = self.templates_data[index]

        try:
            # Import and test the template
            from templates import TEMPLATE_REGISTRY
            template_key = template['file_name']

            if template_key in TEMPLATE_REGISTRY:
                template_class = TEMPLATE_REGISTRY[template_key]
                result = template_class.extract(pdf_path)

                # Show results
                msg = QMessageBox(self)
                msg.setWindowTitle("Test Results")
                msg.setIcon(QMessageBox.Icon.Information)

                if result:
                    text = f"Template matched! Extracted {len(result)} rows.\n\n"
                    if result:
                        text += "First row:\n"
                        for key, value in list(result[0].items())[:5]:
                            text += f"  {key}: {value}\n"
                else:
                    text = "Template did not match this PDF."

                msg.setText(text)
                msg.exec()
            else:
                QMessageBox.warning(
                    self, "Template Not Loaded",
                    "Please refresh templates first."
                )
        except Exception as e:
            QMessageBox.critical(self, "Test Failed", f"Error testing template:\n{e}")

    def _on_browse_sample_pdf(self):
        """Browse for a sample PDF file."""
        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sample Invoice PDF", "", "PDF Files (*.pdf)"
        )

        if pdf_path:
            self.sample_file_edit.setText(pdf_path)

            # Try to extract text
            try:
                import pdfplumber
                with pdfplumber.open(pdf_path) as pdf:
                    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
                    self.sample_text_edit.setPlainText(text[:2000])  # Limit preview
            except ImportError:
                QMessageBox.warning(
                    self, "pdfplumber Not Installed",
                    "Install pdfplumber to auto-extract PDF text:\npip install pdfplumber"
                )
            except Exception as e:
                QMessageBox.warning(self, "PDF Error", f"Could not extract text:\n{e}")

    def _on_generate_template(self):
        """Generate a new template using AI."""
        sample_text = self.sample_text_edit.toPlainText().strip()
        if not sample_text:
            QMessageBox.warning(self, "No Sample", "Please provide sample invoice text.")
            return

        template_name = self.new_template_name.text().strip()
        if not template_name:
            QMessageBox.warning(self, "No Name", "Please enter a template name.")
            return

        # Sanitize name
        template_name = re.sub(r'[^a-zA-Z0-9_]', '_', template_name.lower())

        self.generate_progress.setVisible(True)
        self.generate_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            # Use AI to generate template
            from ai_template_generator import AITemplateGeneratorDialog

            # Create a simple prompt for the AI
            prompt = f"""Generate a Python template class for extracting data from this invoice format.

Sample Invoice Text:
{sample_text[:3000]}

Template Metadata:
- name = "{self.new_supplier_name.text() or template_name}"
- supplier = "{self.new_supplier_name.text()}"
- client = "{self.new_client_name.text()}"
- country = "{self.new_country.text()}"

Generate a complete template class following the OCRMill template format."""

            # For now, show a message that this requires the AI dialog
            self.generate_progress.setVisible(False)
            self.generate_btn.setEnabled(True)

            QMessageBox.information(
                self, "Generate Template",
                "To generate a template with AI, use the AI chat panel after creating a basic template.\n\n"
                "For now, a basic template structure will be created."
            )

            # Generate basic template
            basic_template = self._generate_basic_template(
                template_name,
                self.new_supplier_name.text(),
                self.new_client_name.text(),
                self.new_country.text(),
                sample_text
            )

            self.generated_preview.setPlainText(basic_template)
            self.generated_preview.setVisible(True)
            self.save_new_btn.setEnabled(True)

        except Exception as e:
            self.generate_progress.setVisible(False)
            self.generate_btn.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Failed to generate template:\n{e}")

    def _generate_basic_template(self, name: str, supplier: str, client: str, country: str, sample: str) -> str:
        """Generate a basic template structure."""
        return f'''"""
Template for {supplier or name}
Auto-generated by OCRMill
"""

import re
from templates.base_template import BaseTemplate


class {name.title().replace('_', '')}Template(BaseTemplate):
    """Template for extracting data from {supplier or 'supplier'} invoices."""

    name = "{supplier or name}"
    description = "Template for {supplier or name} invoices"
    supplier = "{supplier}"
    client = "{client}"
    country = "{country}"
    version = "1.0.0"

    # Detection patterns - customize these
    detection_patterns = [
        r"invoice",  # Add patterns that identify this invoice type
    ]

    @classmethod
    def can_handle(cls, text: str) -> bool:
        """Check if this template can handle the given text."""
        text_lower = text.lower()
        return any(re.search(p, text_lower) for p in cls.detection_patterns)

    @classmethod
    def extract(cls, pdf_path: str) -> list:
        """Extract invoice data from the PDF."""
        import pdfplumber

        results = []

        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\\n".join(page.extract_text() or "" for page in pdf.pages)

            # TODO: Implement extraction logic
            # Extract invoice number, items, quantities, prices, etc.

            # Example extraction pattern:
            # invoice_match = re.search(r"Invoice[:\\s#]*(\\w+)", full_text, re.IGNORECASE)
            # invoice_number = invoice_match.group(1) if invoice_match else ""

            # For each line item, create a dict:
            # results.append({{
            #     'invoice_number': invoice_number,
            #     'part_number': part_no,
            #     'description': desc,
            #     'quantity': qty,
            #     'unit_price': price,
            #     'total_price': total,
            # }})

        return results


# Register the template
TEMPLATE = {name.title().replace('_', '')}Template
'''

    def _on_save_new_template(self):
        """Save the newly generated template."""
        template_name = self.new_template_name.text().strip()
        template_name = re.sub(r'[^a-zA-Z0-9_]', '_', template_name.lower())

        if not template_name:
            QMessageBox.warning(self, "No Name", "Please enter a template name.")
            return

        content = self.generated_preview.toPlainText()
        if not content:
            QMessageBox.warning(self, "No Content", "No template content to save.")
            return

        # Save to local templates folder
        local_path = Path(__file__).parent.parent.parent / "templates"
        new_path = local_path / f"{template_name}.py"

        if new_path.exists():
            reply = QMessageBox.question(
                self, "Overwrite?",
                f"Template '{template_name}' already exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        try:
            new_path.write_text(content, encoding='utf-8')
            self._load_templates()
            self.templates_changed.emit()
            self.template_created.emit(template_name, str(new_path))

            QMessageBox.information(self, "Success", f"Template '{template_name}' saved.")
            self._on_back_to_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save template:\n{e}")

    def _on_provider_changed(self, provider: str):
        """Update model options when AI provider changes."""
        self.ai_model_combo.clear()

        models = {
            "Anthropic": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"],
            "OpenAI": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4"],
            "Google Gemini": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"],
            "Groq": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
            "Ollama": ["llama3.2", "codellama", "mistral", "qwen2.5-coder"],
        }

        self.ai_model_combo.addItems(models.get(provider, ["default"]))

    def _on_send_message(self):
        """Send a message to the AI assistant."""
        message = self.chat_input.text().strip()
        if not message:
            return

        # Get API key from config
        provider = self.ai_provider_combo.currentText()
        api_key = self._get_api_key(provider)

        if not api_key:
            QMessageBox.warning(
                self, "API Key Required",
                f"Please configure your {provider} API key in Settings > AI Configuration."
            )
            return

        # Check if we have a template loaded
        current_code = self.code_editor.toPlainText()
        if not current_code.strip():
            QMessageBox.warning(
                self, "No Template",
                "Please select or create a template first."
            )
            return

        # Add user message to display
        self._append_user_message(message)
        self.chat_input.clear()

        # Disable send, enable cancel
        self.send_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)

        # Start AI request in background
        self.chat_thread = AITemplateChatThread(
            provider=provider,
            model=self.ai_model_combo.currentText(),
            api_key=api_key,
            current_code=current_code,
            user_message=message,
            conversation_history=self.conversation_history.copy(),
            invoice_text=self.invoice_text
        )
        self.chat_thread.finished.connect(self._on_ai_response)
        self.chat_thread.error.connect(self._on_ai_error)
        self.chat_thread.start()

        # Add to conversation history
        self.conversation_history.append({"role": "user", "content": message})

    def _get_api_key(self, provider: str) -> str:
        """Get API key for the specified provider."""
        # Try database config first
        key_map = {
            "Anthropic": "anthropic_api_key",
            "OpenAI": "openai_api_key",
            "Google Gemini": "gemini_api_key",
            "Groq": "groq_api_key",
            "Ollama": None  # Ollama doesn't need API key
        }

        config_key = key_map.get(provider)

        if provider == "Ollama":
            return "local"  # Ollama runs locally

        if config_key:
            try:
                api_key = self.db.get_app_config(config_key)
                if api_key:
                    return api_key
            except Exception:
                pass

        # Fall back to environment variables
        env_map = {
            "Anthropic": "ANTHROPIC_API_KEY",
            "OpenAI": "OPENAI_API_KEY",
            "Google Gemini": "GOOGLE_API_KEY",
            "Groq": "GROQ_API_KEY",
        }

        env_key = env_map.get(provider)
        if env_key:
            return os.environ.get(env_key, "")

        return ""

    def _append_user_message(self, message: str):
        """Add a user message to the chat display."""
        is_dark = self.theme_manager.is_dark_theme()
        user_color = "#61afef" if is_dark else "#0066cc"
        self.chat_display.append(
            f'<p style="margin: 8px 0;"><span style="color: {user_color}; font-weight: bold;">You:</span> {message}</p>'
        )
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _append_ai_message(self, message: str):
        """Add an AI message to the chat display."""
        is_dark = self.theme_manager.is_dark_theme()
        ai_color = "#98c379" if is_dark else "#008800"
        # Convert markdown code blocks to HTML
        formatted = self._format_ai_message(message)
        self.chat_display.append(
            f'<p style="margin: 8px 0;"><span style="color: {ai_color}; font-weight: bold;">AI:</span></p>{formatted}'
        )
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _format_ai_message(self, message: str) -> str:
        """Format AI message with code highlighting."""
        is_dark = self.theme_manager.is_dark_theme()
        code_bg = "#1e1e1e" if is_dark else "#f5f5f5"
        code_color = "#d4d4d4" if is_dark else "#333333"

        # Replace code blocks with styled HTML
        def replace_code_block(match):
            code = match.group(1)
            return f'<pre style="background-color: {code_bg}; color: {code_color}; padding: 10px; border-radius: 4px; overflow-x: auto; font-family: Consolas, monospace; font-size: 9pt;">{code}</pre>'

        # Handle ```python ... ``` blocks
        formatted = re.sub(
            r'```(?:python)?\s*(.*?)\s*```',
            replace_code_block,
            message,
            flags=re.DOTALL
        )

        # Handle inline code
        inline_bg = "#2d2d2d" if is_dark else "#e8e8e8"
        formatted = re.sub(
            r'`([^`]+)`',
            f'<code style="background-color: {inline_bg}; padding: 2px 4px; border-radius: 3px;">\1</code>',
            formatted
        )

        # Convert newlines to <br> for non-code text
        formatted = formatted.replace('\n', '<br>')

        return formatted

    def _append_system_message(self, message: str):
        """Add a system message to the chat display."""
        is_dark = self.theme_manager.is_dark_theme()
        sys_color = "#888888" if is_dark else "#666666"
        self.chat_display.append(
            f'<p style="margin: 4px 0; color: {sys_color}; font-style: italic; font-size: 9pt;">{message}</p>'
        )
        self.chat_display.verticalScrollBar().setValue(
            self.chat_display.verticalScrollBar().maximum()
        )

    def _on_ai_response(self, response: str):
        """Handle AI response."""
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        # Add to conversation history
        self.conversation_history.append({"role": "assistant", "content": response})

        # Check for code block in response
        code_match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)

        if code_match:
            extracted_code = code_match.group(1).strip()
            self.pending_code = extracted_code

            # Show response without the code block (replaced with indicator)
            display_response = re.sub(
                r'```python\s*.*?\s*```',
                '[Code block extracted - click "Apply Code" to apply]',
                response,
                flags=re.DOTALL
            )
            self._append_ai_message(display_response)
            self._append_system_message("Code changes ready. Click 'Apply Code' to apply them to the editor.")
            self.apply_code_btn.setEnabled(True)
        else:
            self._append_ai_message(response)
            self.pending_code = None
            self.apply_code_btn.setEnabled(False)

    def _on_ai_error(self, error: str):
        """Handle AI error."""
        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

        is_dark = self.theme_manager.is_dark_theme()
        error_color = "#f14c4c" if is_dark else "#cc0000"
        self.chat_display.append(
            f'<p style="color: {error_color}; margin: 8px 0;"><b>Error:</b> {error}</p>'
        )

    def _on_cancel_chat(self):
        """Cancel the current AI request."""
        if self.chat_thread and self.chat_thread.isRunning():
            self.chat_thread.cancel()
            self.chat_thread.wait(1000)
            self._append_system_message("Request cancelled.")

        self.send_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _on_load_invoice_context(self):
        """Load a sample invoice PDF to provide context for AI."""
        pdf_path, _ = QFileDialog.getOpenFileName(
            self, "Select Sample Invoice PDF", "", "PDF Files (*.pdf)"
        )

        if not pdf_path:
            return

        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                text_parts = []
                for page in pdf.pages[:5]:  # Limit to first 5 pages
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

                self.invoice_text = "\n".join(text_parts)

                # Update status label
                file_name = Path(pdf_path).name
                char_count = len(self.invoice_text)
                self.invoice_status_label.setText(f"✓ {file_name} ({char_count:,} chars)")
                self.invoice_status_label.setStyleSheet("color: #4ec9b0; font-size: 9pt;")

                self._append_system_message(f"Loaded invoice: {file_name} ({char_count:,} characters)")

        except ImportError:
            QMessageBox.warning(
                self, "pdfplumber Not Installed",
                "Install pdfplumber to load PDF invoices:\npip install pdfplumber"
            )
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load invoice:\n{e}")

    def _on_clear_chat(self):
        """Clear the chat display and conversation history."""
        self.chat_display.clear()
        self.conversation_history = []
        self.pending_code = None
        self.apply_code_btn.setEnabled(False)

    def _on_apply_code(self):
        """Apply AI-suggested code to the editor."""
        if not self.pending_code:
            return

        # Validate syntax before applying
        try:
            compile(self.pending_code, '<ai_code>', 'exec')
        except SyntaxError as e:
            reply = QMessageBox.question(
                self, "Syntax Error",
                f"The AI-generated code has a syntax error on line {e.lineno}.\n"
                f"Apply anyway?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                return

        # Apply code to editor
        self.code_editor.setPlainText(self.pending_code)
        self.current_template_modified = True

        self._append_system_message("Code applied to editor.")
        self.pending_code = None
        self.apply_code_btn.setEnabled(False)
        self._validate_code()
