"""
AI Template Generator for OCRMill

Allows users to generate invoice templates using AI models (OpenAI, Anthropic, Google Gemini, Groq).
The AI analyzes sample invoice text and generates a complete template class.
"""

import os
import re
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFormLayout, QLineEdit, QTextEdit, QPlainTextEdit,
    QComboBox, QSpinBox, QCheckBox, QFileDialog, QMessageBox,
    QTabWidget, QWidget, QProgressBar, QApplication, QSplitter,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont

# Base directory for templates
BASE_DIR = Path(__file__).parent

# Try to import AI libraries
try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import google.generativeai as genai
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from groq import Groq
    HAS_GROQ = True
except ImportError:
    HAS_GROQ = False

try:
    import ollama
    HAS_OLLAMA = True
except ImportError:
    HAS_OLLAMA = False

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False


def _check_ollama_running() -> bool:
    """Check if Ollama server is running locally."""
    import urllib.request
    try:
        req = urllib.request.Request('http://localhost:11434/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _get_ollama_models() -> List[str]:
    """Get list of available Ollama models."""
    import urllib.request
    import json
    try:
        req = urllib.request.Request('http://localhost:11434/api/tags', method='GET')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            models = [m['name'] for m in data.get('models', [])]
            return models if models else ["llama3.2", "codellama", "mistral", "qwen2.5-coder"]
    except Exception:
        return ["llama3.2", "codellama", "mistral", "qwen2.5-coder"]


def _install_package(package_name: str, parent=None) -> bool:
    """
    Install a Python package using pip.
    Returns True if installation succeeded, False otherwise.
    """
    try:
        # Use the same Python executable that's running this script
        python_exe = sys.executable

        # Show progress dialog
        progress = QMessageBox(parent)
        progress.setWindowTitle("Installing Package")
        progress.setText(f"Installing {package_name}...")
        progress.setStandardButtons(QMessageBox.StandardButton.NoButton)
        progress.show()
        QApplication.processEvents()

        # Run pip install
        result = subprocess.run(
            [python_exe, "-m", "pip", "install", package_name],
            capture_output=True,
            text=True,
            timeout=120
        )

        progress.close()

        if result.returncode == 0:
            QMessageBox.information(
                parent, "Installation Successful",
                f"The {package_name} package has been installed successfully.\n\n"
                "Please restart the application to use this feature."
            )
            return True
        else:
            QMessageBox.critical(
                parent, "Installation Failed",
                f"Failed to install {package_name}:\n\n{result.stderr}"
            )
            return False

    except subprocess.TimeoutExpired:
        QMessageBox.critical(
            parent, "Installation Timeout",
            f"Installation of {package_name} timed out.\n"
            "Please try installing manually:\n  pip install " + package_name
        )
        return False
    except Exception as e:
        QMessageBox.critical(
            parent, "Installation Error",
            f"Error installing {package_name}:\n\n{str(e)}"
        )
        return False


def _check_and_install_package(package_name: str, import_name: str = None, parent=None) -> bool:
    """
    Check if a package is installed, and offer to install if not.
    Returns True if package is available (installed or just installed), False otherwise.
    """
    if import_name is None:
        import_name = package_name

    try:
        __import__(import_name)
        return True
    except ImportError:
        # Show dialog with install option
        msg_box = QMessageBox(parent)
        msg_box.setWindowTitle("Package Not Installed")
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setText(f"The {package_name} package is not installed.")
        msg_box.setInformativeText("Would you like to install it now?")

        install_btn = msg_box.addButton("Install Now", QMessageBox.ButtonRole.AcceptRole)
        msg_box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == install_btn:
            return _install_package(package_name, parent)

        return False


class AIGeneratorThread(QThread):
    """Background thread for AI template generation."""
    finished = pyqtSignal(str)  # Generated code
    error = pyqtSignal(str)
    progress = pyqtSignal(str)
    stream_update = pyqtSignal(str)  # Streaming text updates (full text so far)
    cancelled = pyqtSignal()  # Emitted when cancelled

    def __init__(self, provider: str, model: str, api_key: str,
                 invoice_text: str, template_name: str, supplier_name: str,
                 country: str, client: str):
        super().__init__()
        self.provider = provider
        self.model = model
        self.api_key = api_key
        self.invoice_text = invoice_text
        self.template_name = template_name
        self.supplier_name = supplier_name
        self.country = country
        self.client = client
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the generation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancellation was requested."""
        return self._cancelled

    def run(self):
        try:
            if self._cancelled:
                self.cancelled.emit()
                return

            self.progress.emit("Preparing prompt...")
            prompt = self._build_prompt()

            if self._cancelled:
                self.cancelled.emit()
                return

            self.progress.emit(f"Calling {self.provider} API...")

            if self.provider == "OpenAI":
                result = self._call_openai(prompt)
            elif self.provider == "Anthropic":
                result = self._call_anthropic(prompt)
            elif self.provider == "Google Gemini":
                result = self._call_gemini(prompt)
            elif self.provider == "Groq":
                result = self._call_groq(prompt)
            elif self.provider == "Ollama (Local)":
                result = self._call_ollama(prompt)
            elif self.provider == "OpenRouter":
                result = self._call_openrouter(prompt)
            elif self.provider == "Together AI":
                result = self._call_together(prompt)
            else:
                raise ValueError(f"Unknown provider: {self.provider}")

            if self._cancelled:
                self.cancelled.emit()
                return

            self.progress.emit("Processing response...")
            code = self._extract_code(result)
            self.finished.emit(code)

        except Exception as e:
            if not self._cancelled:
                self.error.emit(str(e))
            else:
                self.cancelled.emit()

    def _build_prompt(self) -> str:
        """Build the prompt for AI template generation."""
        # Truncate invoice text if too long
        invoice_sample = self.invoice_text[:8000] if len(self.invoice_text) > 8000 else self.invoice_text

        prompt = f'''You are an expert Python developer creating invoice parsing templates for OCRMill.
Analyze this sample invoice text and generate a complete Python template class.

SAMPLE INVOICE TEXT:
```
{invoice_sample}
```

REQUIREMENTS:
1. Template Name: {self.template_name}
2. Supplier Name: {self.supplier_name}
3. Country of Origin: {self.country}
4. Client: {self.client}

Generate a Python class that:
1. Inherits from BaseTemplate
2. Has a can_process() method that identifies this supplier's invoices
3. Has extract_invoice_number() to find the invoice number
4. Has extract_project_number() to find PO/project numbers
5. Has extract_line_items() to extract part numbers, quantities, and prices
6. Uses regex patterns appropriate for this invoice format

The class should follow this structure:

```python
"""
{self.supplier_name} Template

Auto-generated template for invoices from {self.supplier_name}.
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

import re
from typing import List, Dict
from .base_template import BaseTemplate


class {self._to_class_name(self.template_name)}(BaseTemplate):
    """Template for {self.supplier_name} invoices."""

    name = "{self.supplier_name}"
    description = "Invoices from {self.supplier_name}"
    client = "{self.client}"
    version = "1.0.0"
    enabled = True

    extra_columns = ['po_number', 'unit_price', 'description', 'country_origin']

    # Keywords to identify this supplier
    SUPPLIER_KEYWORDS = [
        # Add lowercase keywords here
    ]

    def can_process(self, text: str) -> bool:
        """Check if this is a {self.supplier_name} invoice."""
        text_lower = text.lower()
        for keyword in self.SUPPLIER_KEYWORDS:
            if keyword in text_lower:
                return True
        return False

    def get_confidence_score(self, text: str) -> float:
        """Return confidence score for template matching."""
        if not self.can_process(text):
            return 0.0
        return 0.8

    def extract_invoice_number(self, text: str) -> str:
        """Extract invoice number using regex patterns."""
        patterns = [
            # Add patterns based on the invoice format
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return "UNKNOWN"

    def extract_project_number(self, text: str) -> str:
        """Extract PO/project number."""
        patterns = [
            # Add patterns for PO numbers
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return "UNKNOWN"

    def extract_manufacturer_name(self, text: str) -> str:
        """Return the manufacturer name."""
        return "{self.supplier_name.upper()}"

    def extract_line_items(self, text: str) -> List[Dict]:
        """Extract line items from invoice."""
        items = []
        # Add extraction logic based on the invoice format
        # Look for patterns like: part_number quantity price

        return items

    def post_process_items(self, items: List[Dict]) -> List[Dict]:
        """Post-process - deduplicate and validate."""
        if not items:
            return items

        seen = set()
        unique_items = []

        for item in items:
            key = f"{{item['part_number']}}_{{item['quantity']}}_{{item['total_price']}}"
            if key not in seen:
                seen.add(key)
                # Add country of origin
                item['country_origin'] = '{self.country}'
                unique_items.append(item)

        return unique_items

    def is_packing_list(self, text: str) -> bool:
        """Check if document is only a packing list."""
        text_lower = text.lower()
        if 'packing list' in text_lower and 'invoice' not in text_lower:
            return True
        return False
```

IMPORTANT:
1. Analyze the invoice text carefully to identify the actual patterns used
2. Create specific regex patterns for invoice numbers, PO numbers, and line items
3. The SUPPLIER_KEYWORDS should contain unique identifiers from the invoice
4. The extract_line_items() method should parse the actual table format from the invoice
5. Return ONLY the Python code, no explanations

Generate the complete, working Python template code:
'''
        return prompt

    def _to_class_name(self, template_name: str) -> str:
        """Convert template name to class name."""
        return ''.join(word.title() for word in template_name.split('_')) + 'Template'

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API."""
        try:
            import openai
        except ImportError:
            raise ImportError("openai package not installed. Run: pip install openai")

        client = openai.OpenAI(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert Python developer specializing in invoice parsing and OCR templates."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )
        return response.choices[0].message.content

    def _call_anthropic(self, prompt: str) -> str:
        """Call Anthropic API."""
        try:
            import anthropic
        except ImportError:
            raise ImportError("anthropic package not installed. Run: pip install anthropic")

        client = anthropic.Anthropic(api_key=self.api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        return response.content[0].text

    def _call_gemini(self, prompt: str) -> str:
        """Call Google Gemini API."""
        try:
            import google.generativeai as genai
        except ImportError:
            raise ImportError("google-generativeai package not installed. Run: pip install google-generativeai")

        genai.configure(api_key=self.api_key)
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=4000,
                temperature=0.3
            )
        )
        return response.text

    def _call_groq(self, prompt: str) -> str:
        """Call Groq API."""
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("groq package not installed. Run: pip install groq")

        client = Groq(api_key=self.api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an expert Python developer specializing in invoice parsing and OCR templates."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=4000,
            temperature=0.3
        )
        return response.choices[0].message.content

    def _call_ollama(self, prompt: str) -> str:
        """Call local Ollama API."""
        import urllib.request
        import json

        # Check if Ollama is running
        if not _check_ollama_running():
            raise ConnectionError(
                "Ollama is not running. Please start Ollama first.\n\n"
                "To start Ollama:\n"
                "1. Install from https://ollama.ai\n"
                "2. Run 'ollama serve' in terminal\n"
                "3. Pull a model: 'ollama pull llama3.2'"
            )

        url = 'http://localhost:11434/api/generate'
        data = json.dumps({
            'model': self.model,
            'prompt': f"You are an expert Python developer specializing in invoice parsing and OCR templates.\n\n{prompt}",
            'stream': False,
            'options': {
                'temperature': 0.3,
                'num_predict': 4000
            }
        }).encode('utf-8')

        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})

        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                result = json.loads(response.read().decode())
                return result.get('response', '')
        except Exception as e:
            raise RuntimeError(f"Ollama API error: {e}")

    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API (access to many models via single API)."""
        import urllib.request
        import json

        url = 'https://openrouter.ai/api/v1/chat/completions'
        data = json.dumps({
            'model': self.model,
            'messages': [
                {"role": "system", "content": "You are an expert Python developer specializing in invoice parsing and OCR templates."},
                {"role": "user", "content": prompt}
            ],
            'max_tokens': 4000,
            'temperature': 0.3
        }).encode('utf-8')

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'HTTP-Referer': 'https://ocrmill.processlogiclabs.com',
            'X-Title': 'OCRMill Template Generator'
        }

        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return result['choices'][0]['message']['content']
        except urllib.request.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            raise RuntimeError(f"OpenRouter API error: {error_body}")

    def _call_together(self, prompt: str) -> str:
        """Call Together AI API."""
        import urllib.request
        import json

        url = 'https://api.together.xyz/v1/chat/completions'
        data = json.dumps({
            'model': self.model,
            'messages': [
                {"role": "system", "content": "You are an expert Python developer specializing in invoice parsing and OCR templates."},
                {"role": "user", "content": prompt}
            ],
            'max_tokens': 4000,
            'temperature': 0.3
        }).encode('utf-8')

        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }

        req = urllib.request.Request(url, data=data, headers=headers)

        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode())
                return result['choices'][0]['message']['content']
        except urllib.request.HTTPError as e:
            error_body = e.read().decode() if e.fp else str(e)
            raise RuntimeError(f"Together AI API error: {error_body}")

    def _extract_code(self, response: str) -> str:
        """Extract Python code from AI response."""
        # Try to find code block
        code_match = re.search(r'```python\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Try without language specifier
        code_match = re.search(r'```\s*(.*?)\s*```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()

        # Return the whole response if no code blocks found
        # but try to clean it up
        lines = response.split('\n')
        code_lines = []
        in_code = False

        for line in lines:
            if line.strip().startswith('"""') or line.strip().startswith('import ') or line.strip().startswith('from '):
                in_code = True
            if in_code:
                code_lines.append(line)

        if code_lines:
            return '\n'.join(code_lines)

        return response


class AITemplateGeneratorDialog(QDialog):
    """
    Dialog for generating invoice templates using AI models.

    Supports:
    - OpenAI (GPT-4, GPT-3.5)
    - Anthropic (Claude)
    - Google Gemini
    - Groq
    """

    template_created = pyqtSignal(str, str)  # template_name, file_path

    def __init__(self, parent=None, db=None):
        super().__init__(parent)
        self.generator_thread = None
        self.invoice_text = ""
        self.db = db  # PartsDatabase instance for saving API keys

        self.setWindowTitle("AI Template Generator")
        self.setMinimumSize(1100, 750)
        self.setup_ui()
        self.load_settings()

    def setup_ui(self):
        """Build the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel("AI Template Generator")
        header.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        layout.addWidget(header)

        desc = QLabel(
            "Use AI to generate new OCR templates from sample invoices."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #7f8c8d; margin-bottom: 15px;")
        layout.addWidget(desc)

        # AI Provider Settings
        provider_group = QGroupBox("AI Provider")
        provider_layout = QFormLayout()

        self.provider_combo = QComboBox()
        # Available providers - status indicator will show if they're available
        providers = ["OpenAI", "Anthropic", "Google Gemini", "Groq", "Ollama (Local)", "OpenRouter", "Together AI"]
        self.provider_combo.addItems(providers)
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        provider_layout.addRow("Provider:", self.provider_combo)

        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        provider_layout.addRow("Model:", self.model_combo)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Enter API key")
        self.api_key_edit.textChanged.connect(self._update_status_indicator)
        provider_layout.addRow("API Key:", self.api_key_edit)

        # Status indicator row
        status_row = QHBoxLayout()
        self.status_indicator = QLabel("●")
        self.status_indicator.setFixedWidth(20)
        self.status_label = QLabel("Checking...")
        self.check_status_btn = QPushButton("Check Status")
        self.check_status_btn.setFixedWidth(100)
        self.check_status_btn.clicked.connect(self._update_status_indicator)
        status_row.addWidget(self.status_indicator)
        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self.check_status_btn)
        provider_layout.addRow("Status:", status_row)

        provider_group.setLayout(provider_layout)
        layout.addWidget(provider_group)

        # Update models for initial provider
        self.on_provider_changed(self.provider_combo.currentText())

        # Initial status check
        self._update_status_indicator()

        # Invoice Input
        input_group = QGroupBox("Sample Invoice")
        input_layout = QVBoxLayout()

        # File selection row
        file_row = QHBoxLayout()
        self.pdf_path_edit = QLineEdit()
        self.pdf_path_edit.setPlaceholderText("Select a PDF invoice or paste text below...")
        self.pdf_path_edit.setReadOnly(True)
        file_row.addWidget(self.pdf_path_edit, stretch=1)

        browse_btn = QPushButton("Browse PDF...")
        browse_btn.clicked.connect(self.browse_pdf)
        file_row.addWidget(browse_btn)

        input_layout.addLayout(file_row)

        self.invoice_text_edit = QPlainTextEdit()
        self.invoice_text_edit.setPlaceholderText(
            "Paste invoice text here, or load from PDF above.\n\n"
            "The AI will analyze this text to create extraction patterns."
        )
        self.invoice_text_edit.setFont(QFont("Courier New", 9))
        input_layout.addWidget(self.invoice_text_edit)

        input_group.setLayout(input_layout)
        layout.addWidget(input_group, stretch=1)

        # Template Settings
        settings_group = QGroupBox("Template Settings")
        settings_layout = QFormLayout()

        self.template_name_edit = QLineEdit()
        self.template_name_edit.setPlaceholderText("e.g., acme_corp (lowercase with underscores)")
        settings_layout.addRow("Template Name:", self.template_name_edit)

        self.supplier_name_edit = QLineEdit()
        self.supplier_name_edit.setPlaceholderText("e.g., Acme Corporation")
        settings_layout.addRow("Supplier Name:", self.supplier_name_edit)

        self.client_edit = QLineEdit()
        self.client_edit.setPlaceholderText("e.g., Your Company Name")
        settings_layout.addRow("Client:", self.client_edit)

        self.country_edit = QLineEdit()
        self.country_edit.setPlaceholderText("e.g., CHINA, INDIA, USA")
        settings_layout.addRow("Country of Origin:", self.country_edit)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Generated Code Preview
        preview_group = QGroupBox("Generated Template (Preview)")
        preview_layout = QVBoxLayout()

        self.code_preview = QPlainTextEdit()
        self.code_preview.setReadOnly(True)
        self.code_preview.setFont(QFont("Courier New", 9))
        self.code_preview.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                padding: 5px;
            }
        """)
        self.code_preview.setPlaceholderText("Generated template code will appear here...")
        preview_layout.addWidget(self.code_preview)

        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, stretch=1)

        # Action buttons
        btn_layout = QHBoxLayout()

        self.generate_btn = QPushButton("Generate Template")
        self.generate_btn.setStyleSheet("""
            QPushButton {
                background-color: #9b59b6;
                color: white;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #8e44ad;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_template)
        btn_layout.addWidget(self.generate_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.cancel_btn.clicked.connect(self.cancel_generation)
        self.cancel_btn.setVisible(False)
        btn_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Template")
        self.save_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-weight: bold;
                padding: 10px 25px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
        """)
        self.save_btn.clicked.connect(self.save_template)
        self.save_btn.setEnabled(False)
        btn_layout.addWidget(self.save_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _get_saved_api_key(self, provider: str) -> str:
        """Get saved API key from database."""
        if self.db:
            try:
                return self.db.get_config(f'api_key_{provider}') or ""
            except Exception:
                pass
        return ""

    def _save_api_key(self, provider: str, api_key: str):
        """Save API key to database."""
        if self.db:
            try:
                self.db.set_config(f'api_key_{provider}', api_key)
            except Exception as e:
                print(f"Failed to save API key: {e}")

    def _update_status_indicator(self, _=None):
        """Update the status indicator based on current provider and settings."""
        provider = self.provider_combo.currentText()

        if provider == "OpenAI":
            # Check if openai package is installed
            try:
                import openai
            except ImportError:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Package not installed - click Generate to install")
                self.status_label.setStyleSheet("color: #e74c3c;")
                return

            api_key = self.api_key_edit.text().strip()
            if api_key:
                if api_key.startswith("sk-"):
                    self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Ready - API key configured")
                    self.status_label.setStyleSheet("color: #27ae60;")
                else:
                    self.status_indicator.setStyleSheet("color: #f39c12; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Warning - API key format looks incorrect")
                    self.status_label.setStyleSheet("color: #f39c12;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Not ready - Enter OpenAI API key")
                self.status_label.setStyleSheet("color: #e74c3c;")

        elif provider == "Anthropic":
            # Check if anthropic package is installed
            try:
                import anthropic
            except ImportError:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Package not installed - click Generate to install")
                self.status_label.setStyleSheet("color: #e74c3c;")
                return

            api_key = self.api_key_edit.text().strip()
            if api_key:
                if api_key.startswith("sk-ant-"):
                    self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Ready - API key configured")
                    self.status_label.setStyleSheet("color: #27ae60;")
                else:
                    self.status_indicator.setStyleSheet("color: #f39c12; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Warning - API key format looks incorrect")
                    self.status_label.setStyleSheet("color: #f39c12;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Not ready - Enter Anthropic API key")
                self.status_label.setStyleSheet("color: #e74c3c;")

        elif provider == "Google Gemini":
            # Check if google-generativeai package is installed
            try:
                import google.generativeai
            except ImportError:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Package not installed - click Generate to install")
                self.status_label.setStyleSheet("color: #e74c3c;")
                return

            api_key = self.api_key_edit.text().strip()
            if api_key:
                if api_key.startswith("AI"):
                    self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Ready - API key configured")
                    self.status_label.setStyleSheet("color: #27ae60;")
                else:
                    self.status_indicator.setStyleSheet("color: #f39c12; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Warning - API key format looks incorrect")
                    self.status_label.setStyleSheet("color: #f39c12;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Not ready - Enter Google AI API key")
                self.status_label.setStyleSheet("color: #e74c3c;")

        elif provider == "Groq":
            # Check if groq package is installed
            try:
                from groq import Groq
            except ImportError:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Package not installed - click Generate to install")
                self.status_label.setStyleSheet("color: #e74c3c;")
                return

            api_key = self.api_key_edit.text().strip()
            if api_key:
                if api_key.startswith("gsk_"):
                    self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Ready - API key configured")
                    self.status_label.setStyleSheet("color: #27ae60;")
                else:
                    self.status_indicator.setStyleSheet("color: #f39c12; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Warning - API key format looks incorrect")
                    self.status_label.setStyleSheet("color: #f39c12;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Not ready - Enter Groq API key")
                self.status_label.setStyleSheet("color: #e74c3c;")

        elif provider == "Ollama (Local)":
            # Check if Ollama is running
            if _check_ollama_running():
                self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Ready - Ollama server running (FREE, no API key needed)")
                self.status_label.setStyleSheet("color: #27ae60;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Ollama not running - start with 'ollama serve'")
                self.status_label.setStyleSheet("color: #e74c3c;")

        elif provider == "OpenRouter":
            api_key = self.api_key_edit.text().strip()
            if api_key:
                if api_key.startswith("sk-or-"):
                    self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Ready - API key configured")
                    self.status_label.setStyleSheet("color: #27ae60;")
                else:
                    self.status_indicator.setStyleSheet("color: #f39c12; font-size: 16px; font-weight: bold;")
                    self.status_label.setText("Warning - API key format looks incorrect")
                    self.status_label.setStyleSheet("color: #f39c12;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Not ready - Get free key at openrouter.ai")
                self.status_label.setStyleSheet("color: #e74c3c;")

        elif provider == "Together AI":
            api_key = self.api_key_edit.text().strip()
            if api_key:
                self.status_indicator.setStyleSheet("color: #27ae60; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Ready - API key configured")
                self.status_label.setStyleSheet("color: #27ae60;")
            else:
                self.status_indicator.setStyleSheet("color: #e74c3c; font-size: 16px; font-weight: bold;")
                self.status_label.setText("Not ready - Get key at together.ai ($25 free credit)")
                self.status_label.setStyleSheet("color: #e74c3c;")

    def on_provider_changed(self, provider: str):
        """Update model list when provider changes."""
        self.model_combo.clear()

        if provider == "OpenAI":
            self.model_combo.addItems(["gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"])
            self.api_key_edit.setEnabled(True)
            self.api_key_edit.setPlaceholderText("Enter OpenAI API key")
            # Try to load from database first, then environment
            saved_key = self._get_saved_api_key('openai')
            if saved_key:
                self.api_key_edit.setText(saved_key)
            elif os.environ.get('OPENAI_API_KEY'):
                self.api_key_edit.setText(os.environ['OPENAI_API_KEY'])
        elif provider == "Anthropic":
            self.model_combo.addItems(["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"])
            self.api_key_edit.setEnabled(True)
            self.api_key_edit.setPlaceholderText("Enter Anthropic API key")
            # Try to load from database first, then environment
            saved_key = self._get_saved_api_key('anthropic')
            if saved_key:
                self.api_key_edit.setText(saved_key)
            elif os.environ.get('ANTHROPIC_API_KEY'):
                self.api_key_edit.setText(os.environ['ANTHROPIC_API_KEY'])
        elif provider == "Google Gemini":
            self.model_combo.addItems(["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"])
            self.api_key_edit.setEnabled(True)
            self.api_key_edit.setPlaceholderText("Enter Google AI API key")
            # Try to load from database first, then environment
            saved_key = self._get_saved_api_key('gemini')
            if saved_key:
                self.api_key_edit.setText(saved_key)
            elif os.environ.get('GOOGLE_API_KEY'):
                self.api_key_edit.setText(os.environ['GOOGLE_API_KEY'])
        elif provider == "Groq":
            self.model_combo.addItems(["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"])
            self.api_key_edit.setEnabled(True)
            self.api_key_edit.setPlaceholderText("Enter Groq API key (FREE tier available)")
            # Try to load from database first, then environment
            saved_key = self._get_saved_api_key('groq')
            if saved_key:
                self.api_key_edit.setText(saved_key)
            elif os.environ.get('GROQ_API_KEY'):
                self.api_key_edit.setText(os.environ['GROQ_API_KEY'])

        elif provider == "Ollama (Local)":
            # Get available models from Ollama
            models = _get_ollama_models()
            self.model_combo.addItems(models)
            self.api_key_edit.setEnabled(False)
            self.api_key_edit.setPlaceholderText("No API key needed - runs locally FREE")
            self.api_key_edit.setText("")

        elif provider == "OpenRouter":
            # OpenRouter provides access to many models - include some free/cheap options
            self.model_combo.addItems([
                "meta-llama/llama-3.2-3b-instruct:free",  # Free
                "meta-llama/llama-3.1-8b-instruct:free",  # Free
                "mistralai/mistral-7b-instruct:free",  # Free
                "google/gemma-2-9b-it:free",  # Free
                "anthropic/claude-3.5-sonnet",
                "openai/gpt-4o",
                "meta-llama/llama-3.3-70b-instruct",
                "deepseek/deepseek-chat",
                "qwen/qwen-2.5-coder-32b-instruct"
            ])
            self.api_key_edit.setEnabled(True)
            self.api_key_edit.setPlaceholderText("Enter OpenRouter API key (has free models)")
            saved_key = self._get_saved_api_key('openrouter')
            if saved_key:
                self.api_key_edit.setText(saved_key)
            elif os.environ.get('OPENROUTER_API_KEY'):
                self.api_key_edit.setText(os.environ['OPENROUTER_API_KEY'])

        elif provider == "Together AI":
            # Together AI - $25 free credit for new users
            self.model_combo.addItems([
                "meta-llama/Llama-3.3-70B-Instruct-Turbo",
                "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
                "Qwen/Qwen2.5-Coder-32B-Instruct",
                "deepseek-ai/DeepSeek-V3",
                "mistralai/Mixtral-8x22B-Instruct-v0.1",
                "codellama/CodeLlama-34b-Instruct-hf"
            ])
            self.api_key_edit.setEnabled(True)
            self.api_key_edit.setPlaceholderText("Enter Together AI key ($25 free credit)")
            saved_key = self._get_saved_api_key('together')
            if saved_key:
                self.api_key_edit.setText(saved_key)
            elif os.environ.get('TOGETHER_API_KEY'):
                self.api_key_edit.setText(os.environ['TOGETHER_API_KEY'])

        # Update status indicator after provider change
        self._update_status_indicator()

    def browse_pdf(self):
        """Browse for PDF file and extract text."""
        if not HAS_PDFPLUMBER:
            # Try to install pdfplumber
            if not _check_and_install_package("pdfplumber", parent=self):
                return

        path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice PDF",
            str(Path.home()),
            "PDF Files (*.pdf);;All Files (*.*)"
        )

        if not path:
            return

        try:
            self.pdf_path_edit.setText(path)

            # Extract text from PDF
            import pdfplumber
            text_parts = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages[:5]:  # First 5 pages
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)

            full_text = '\n\n'.join(text_parts)
            self.invoice_text_edit.setPlainText(full_text)

            # Try to auto-detect supplier name
            self._auto_detect_supplier(full_text)

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to extract PDF text:\n{e}")

    def _auto_detect_supplier(self, text: str):
        """Try to auto-detect supplier name from invoice text."""
        # Look for common patterns
        lines = text.split('\n')

        # First few non-empty lines often contain company name
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 5 and len(line) < 60:
                # Skip lines that look like addresses or dates
                if re.match(r'^[\d\s\-/]+$', line):  # Just numbers
                    continue
                if re.search(r'\d{4}', line):  # Contains year
                    continue
                if '@' in line or 'www.' in line.lower():  # Email/web
                    continue

                # This might be a company name
                if not self.supplier_name_edit.text():
                    self.supplier_name_edit.setText(line)
                    # Generate template name
                    template_name = re.sub(r'[^a-z0-9]+', '_', line.lower()).strip('_')
                    self.template_name_edit.setText(template_name[:30])
                break

    def generate_template(self):
        """Start AI template generation."""
        # Validate inputs
        invoice_text = self.invoice_text_edit.toPlainText().strip()
        if not invoice_text:
            QMessageBox.warning(self, "Missing Input", "Please provide invoice text or load a PDF.")
            return

        template_name = self.template_name_edit.text().strip()
        if not template_name:
            QMessageBox.warning(self, "Missing Input", "Please enter a template name.")
            return

        if not re.match(r'^[a-z][a-z0-9_]*$', template_name):
            QMessageBox.warning(
                self, "Invalid Name",
                "Template name must be lowercase, start with a letter, "
                "and contain only letters, numbers, and underscores."
            )
            return

        supplier_name = self.supplier_name_edit.text().strip()
        if not supplier_name:
            QMessageBox.warning(self, "Missing Input", "Please enter a supplier name.")
            return

        provider = self.provider_combo.currentText()
        api_key = self.api_key_edit.text().strip()

        # Check if required package is installed
        if provider == "OpenAI":
            if not _check_and_install_package("openai", parent=self):
                return
        elif provider == "Anthropic":
            if not _check_and_install_package("anthropic", parent=self):
                return
        elif provider == "Google Gemini":
            if not _check_and_install_package("google-generativeai", "google.generativeai", parent=self):
                return
        elif provider == "Groq":
            if not _check_and_install_package("groq", parent=self):
                return
        elif provider == "Ollama (Local)":
            # Check if Ollama is running
            if not _check_ollama_running():
                QMessageBox.warning(
                    self, "Ollama Not Running",
                    "Ollama server is not running.\n\n"
                    "To start Ollama:\n"
                    "1. Install from https://ollama.ai\n"
                    "2. Run 'ollama serve' in terminal\n"
                    "3. Pull a model: 'ollama pull llama3.2'"
                )
                return

        # API key validation (skip for Ollama which runs locally)
        if provider != "Ollama (Local)" and not api_key:
            QMessageBox.warning(self, "Missing API Key", f"Please enter your {provider} API key.")
            return

        # Save API key immediately when starting generation
        if provider == "OpenAI":
            self._save_api_key('openai', api_key)
        elif provider == "Anthropic":
            self._save_api_key('anthropic', api_key)
        elif provider == "Google Gemini":
            self._save_api_key('gemini', api_key)
        elif provider == "Groq":
            self._save_api_key('groq', api_key)
        elif provider == "OpenRouter":
            self._save_api_key('openrouter', api_key)
        elif provider == "Together AI":
            self._save_api_key('together', api_key)

        # Start generation
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Generating...")
        self.generate_btn.setVisible(False)
        self.cancel_btn.setVisible(True)
        self.save_btn.setEnabled(False)

        self.generator_thread = AIGeneratorThread(
            provider=provider,
            model=self.model_combo.currentText(),
            api_key=api_key,
            invoice_text=invoice_text,
            template_name=template_name,
            supplier_name=supplier_name,
            country=self.country_edit.text().strip() or "UNKNOWN",
            client=self.client_edit.text().strip() or "Universal"
        )
        self.generator_thread.finished.connect(self.on_generation_complete)
        self.generator_thread.error.connect(self.on_generation_error)
        self.generator_thread.progress.connect(self.on_progress)
        self.generator_thread.stream_update.connect(self.on_stream_update)
        self.generator_thread.cancelled.connect(self.on_generation_cancelled)
        self.generator_thread.start()

    def on_progress(self, message: str):
        """Update progress message."""
        self.progress_bar.setFormat(message)

    def on_stream_update(self, text: str):
        """Update preview with streaming text."""
        # Show raw streaming text in preview (will be processed on completion)
        self.code_preview.setPlainText(text)
        # Scroll to bottom to show latest content
        scrollbar = self.code_preview.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def on_generation_complete(self, code: str):
        """Handle successful generation."""
        self.progress_bar.setVisible(False)
        self.generate_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.save_btn.setEnabled(True)

        self.code_preview.setPlainText(code)

        QMessageBox.information(
            self, "Generation Complete",
            "Template generated successfully!\n\n"
            "Review the code in the preview, then click 'Save Template' to save it."
        )

    def on_generation_error(self, error: str):
        """Handle generation error."""
        self.progress_bar.setVisible(False)
        self.generate_btn.setVisible(True)
        self.cancel_btn.setVisible(False)

        QMessageBox.critical(
            self, "Generation Error",
            f"Failed to generate template:\n\n{error}"
        )

    def cancel_generation(self):
        """Cancel the ongoing generation."""
        if self.generator_thread and self.generator_thread.isRunning():
            self.progress_bar.setFormat("Cancelling...")
            self.cancel_btn.setEnabled(False)
            self.generator_thread.cancel()
            # Force terminate after a short wait if still running
            if not self.generator_thread.wait(2000):  # Wait 2 seconds
                self.generator_thread.terminate()
                self.generator_thread.wait()
            self.on_generation_cancelled()

    def on_generation_cancelled(self):
        """Handle cancelled generation."""
        self.progress_bar.setVisible(False)
        self.generate_btn.setVisible(True)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setEnabled(True)
        self.progress_bar.setFormat("Cancelled")

    def save_template(self):
        """Save the generated template."""
        code = self.code_preview.toPlainText().strip()
        if not code:
            QMessageBox.warning(self, "No Code", "No template code to save.")
            return

        template_name = self.template_name_edit.text().strip()

        # Determine templates directory
        templates_dir = Path(__file__).parent / 'templates'
        if not templates_dir.exists():
            templates_dir.mkdir(parents=True, exist_ok=True)

        file_path = templates_dir / f"{template_name}.py"

        # Check if file already exists
        if file_path.exists():
            reply = QMessageBox.question(
                self, "File Exists",
                f"Template '{template_name}' already exists.\n\nOverwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Save the file
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code)

            # Save AI metadata alongside the template
            metadata_path = file_path.with_suffix('.ai_meta.json')
            metadata = {
                'provider': self.provider_combo.currentText(),
                'model': self.model_combo.currentText(),
                'template_name': template_name,
                'supplier_name': self.supplier_name_edit.text().strip(),
                'country': self.country_edit.text().strip(),
                'client': self.client_edit.text().strip(),
                'invoice_text': self.invoice_text_edit.toPlainText().strip()[:5000],  # Limit size
                'created_at': datetime.now().isoformat(),
                'conversation_history': []  # For future chat modifications
            }
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)

            QMessageBox.information(
                self, "Template Saved",
                f"Template saved successfully!\n\n"
                f"File: {file_path}\n\n"
                f"The template will be available after refreshing templates."
            )

            # Emit signal
            self.template_created.emit(template_name, str(file_path))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save template:\n{e}")

    def load_settings(self):
        """Load saved settings (API keys, preferred provider) from database."""
        # Load API key for current provider
        current_provider = self.provider_combo.currentText()
        provider_key = current_provider.lower().replace(" ", "").replace("google", "")

        saved_key = self._get_saved_api_key(provider_key)
        if saved_key:
            self.api_key_edit.setText(saved_key)
        elif current_provider == "OpenAI" and os.environ.get('OPENAI_API_KEY'):
            self.api_key_edit.setText(os.environ['OPENAI_API_KEY'])
        elif current_provider == "Anthropic" and os.environ.get('ANTHROPIC_API_KEY'):
            self.api_key_edit.setText(os.environ['ANTHROPIC_API_KEY'])
        elif current_provider == "Google Gemini" and os.environ.get('GOOGLE_API_KEY'):
            self.api_key_edit.setText(os.environ['GOOGLE_API_KEY'])
        elif current_provider == "Groq" and os.environ.get('GROQ_API_KEY'):
            self.api_key_edit.setText(os.environ['GROQ_API_KEY'])
