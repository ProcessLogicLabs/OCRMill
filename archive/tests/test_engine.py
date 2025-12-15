"""Test the actual engine."""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
from config_manager import ConfigManager
from invoice_processor_gui import ProcessorEngine

config = ConfigManager()

def log(msg):
    print(msg)

engine = ProcessorEngine(config, log_callback=log)

pdf_path = Path("input/Failed/2025601736 - mmcité usa - US25A0203 (5).pdf")

print(f"Processing: {pdf_path}")
print("=" * 80)

items = engine.process_pdf(pdf_path)

print("\n" + "=" * 80)
print(f"Result: {len(items)} items")
if items:
    print(f"First item: {items[0]}")
