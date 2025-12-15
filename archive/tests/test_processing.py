"""
Quick test script to verify the processor works correctly.
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from pathlib import Path
from config_manager import ConfigManager
from invoice_processor_gui import ProcessorEngine

def test_processing():
    """Test the processing engine."""
    print("Testing Invoice Processor...")
    print("=" * 60)

    # Create config
    config = ConfigManager()

    # Create engine with console logging
    def log_to_console(msg):
        print(msg)

    engine = ProcessorEngine(config, log_callback=log_to_console)

    # Get input/output folders
    input_folder = Path(config.input_folder)
    output_folder = Path(config.output_folder)

    print(f"\nInput folder: {input_folder.absolute()}")
    print(f"Output folder: {output_folder.absolute()}")
    print(f"\nTemplates loaded: {len(engine.templates)}")
    for name, template in engine.templates.items():
        enabled = config.get_template_enabled(name) and template.enabled
        status = "✓ Enabled" if enabled else "✗ Disabled"
        print(f"  - {name}: {status}")

    print("\n" + "=" * 60)
    print("Processing PDFs...")
    print("=" * 60)

    # Process folder
    count = engine.process_folder(input_folder, output_folder)

    print("\n" + "=" * 60)
    print(f"Processing complete: {count} files processed successfully")
    print("=" * 60)

    # Check results
    processed_folder = input_folder / "Processed"
    failed_folder = input_folder / "Failed"

    if processed_folder.exists():
        processed_count = len(list(processed_folder.glob("*.pdf")))
        print(f"\nProcessed folder: {processed_count} PDFs")

    if failed_folder.exists():
        failed_count = len(list(failed_folder.glob("*.pdf")))
        print(f"Failed folder: {failed_count} PDFs")

    if output_folder.exists():
        csv_count = len(list(output_folder.glob("**/*.csv")))
        print(f"Output folder: {csv_count} CSV files")

if __name__ == "__main__":
    test_processing()
