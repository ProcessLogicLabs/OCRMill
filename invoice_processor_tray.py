"""
Invoice PDF Processor - System Tray Application
Provides a system tray icon with controls for the invoice processor.
"""

import threading
import time
from pathlib import Path
from datetime import datetime

import pystray
from PIL import Image, ImageDraw
from pystray import MenuItem as item

# Import the processor functions
from invoice_processor import (
    process_folder, setup_folders, 
    INPUT_FOLDER, OUTPUT_FOLDER, PROCESSED_FOLDER, POLL_INTERVAL,
    logger, __version__
)


class InvoiceProcessorTray:
    def __init__(self):
        self.running = False
        self.processing_thread = None
        self.files_processed = 0
        self.last_check = None
        self.icon = None
        
    def create_icon_image(self, color='green'):
        """Create a simple icon for the system tray."""
        # Create a 64x64 image
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        
        # Draw a document icon shape
        colors = {
            'green': (34, 139, 34),    # Running
            'yellow': (255, 193, 7),   # Processing
            'red': (220, 53, 69),      # Stopped
            'blue': (0, 123, 255)      # Idle
        }
        fill_color = colors.get(color, colors['blue'])
        
        # Document shape
        draw.rectangle([10, 5, 54, 59], fill=fill_color, outline=(0, 0, 0))
        # Folded corner
        draw.polygon([(40, 5), (54, 5), (54, 19), (40, 19)], fill=(255, 255, 255))
        draw.polygon([(40, 5), (54, 19), (40, 19)], fill=(200, 200, 200))
        # Lines on document
        draw.rectangle([16, 25, 48, 29], fill=(255, 255, 255))
        draw.rectangle([16, 35, 48, 39], fill=(255, 255, 255))
        draw.rectangle([16, 45, 38, 49], fill=(255, 255, 255))
        
        return image
    
    def get_status_text(self):
        """Get current status text."""
        version_str = f"Invoice Processor v{__version__}"
        if self.running:
            status = f"{version_str}\nRunning - {self.files_processed} files processed"
            if self.last_check:
                status += f"\nLast check: {self.last_check}"
            return status
        return f"{version_str}\nStopped"
    
    def processing_loop(self):
        """Main processing loop that runs in a background thread."""
        setup_folders()
        logger.info("Tray processor started")
        
        while self.running:
            try:
                # Check for PDFs
                pdf_count = len(list(INPUT_FOLDER.glob("*.pdf")))
                self.last_check = datetime.now().strftime("%H:%M:%S")
                
                if pdf_count > 0:
                    # Update icon to yellow (processing)
                    if self.icon:
                        self.icon.icon = self.create_icon_image('yellow')
                    
                    # Process files
                    before_count = self.files_processed
                    process_folder()
                    
                    # Count processed (files that were in input but now moved)
                    new_pdf_count = len(list(INPUT_FOLDER.glob("*.pdf")))
                    self.files_processed += (pdf_count - new_pdf_count)
                    
                    # Update icon back to green
                    if self.icon:
                        self.icon.icon = self.create_icon_image('green')
                        self.icon.title = f"Invoice Processor\n{self.get_status_text()}"
                
                time.sleep(POLL_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in processing loop: {e}")
                time.sleep(POLL_INTERVAL)
        
        logger.info("Tray processor stopped")
    
    def start_processing(self, icon=None, item=None):
        """Start the processing thread."""
        if not self.running:
            self.running = True
            self.processing_thread = threading.Thread(target=self.processing_loop, daemon=True)
            self.processing_thread.start()
            if self.icon:
                self.icon.icon = self.create_icon_image('green')
                self.icon.title = f"Invoice Processor\n{self.get_status_text()}"
            logger.info("Processing started via tray")
    
    def stop_processing(self, icon=None, item=None):
        """Stop the processing thread."""
        self.running = False
        if self.icon:
            self.icon.icon = self.create_icon_image('red')
            self.icon.title = f"Invoice Processor\nStopped"
        logger.info("Processing stopped via tray")
    
    def open_input_folder(self, icon=None, item=None):
        """Open the input folder in Explorer."""
        import os
        os.startfile(INPUT_FOLDER.absolute())
    
    def open_output_folder(self, icon=None, item=None):
        """Open the output folder in Explorer."""
        import os
        os.startfile(OUTPUT_FOLDER.absolute())
    
    def exit_app(self, icon=None, item=None):
        """Exit the application."""
        self.running = False
        if self.icon:
            self.icon.stop()
    
    def create_menu(self):
        """Create the system tray menu."""
        return pystray.Menu(
            item('Status', lambda: None, enabled=False),
            item(lambda text: self.get_status_text(), lambda: None, enabled=False),
            pystray.Menu.SEPARATOR,
            item('Start Processing', self.start_processing, 
                 visible=lambda item: not self.running),
            item('Stop Processing', self.stop_processing,
                 visible=lambda item: self.running),
            pystray.Menu.SEPARATOR,
            item('Open Input Folder', self.open_input_folder),
            item('Open Output Folder', self.open_output_folder),
            pystray.Menu.SEPARATOR,
            item('Exit', self.exit_app)
        )
    
    def run(self):
        """Run the system tray application."""
        # Create the icon
        self.icon = pystray.Icon(
            "invoice_processor",
            self.create_icon_image('red'),
            "Invoice Processor\nStopped",
            self.create_menu()
        )
        
        # Auto-start processing
        self.start_processing()
        
        # Run the icon (this blocks)
        self.icon.run()


def main():
    print("Starting Invoice Processor System Tray...")
    print("Look for the icon in your system tray.")
    print("Right-click the icon for options.\n")
    
    app = InvoiceProcessorTray()
    app.run()


if __name__ == "__main__":
    main()
