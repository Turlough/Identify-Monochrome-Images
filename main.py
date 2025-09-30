import sys
import os
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple
from PIL import Image, ImageOps
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QScrollArea, QLabel, 
                            QCheckBox, QMenuBar, QFileDialog, QMessageBox,
                            QFrame, QSizePolicy, QPushButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QAction, QFont
from color_detector import ColorDetector
from exporter import export_from_import_file
from thumbnails import ThumbnailWidget

from color_analyser import ColorAnalysisThread
from image_converter import ImageConverter

class MonochromeDetector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document_data = []
        self.image_files = []
        self.thumbnail_widgets = []
        self.selected_images = set()
        self.converter_thread = None
        self.color_analysis_thread = None
        
        self.setWindowTitle("Monochrome Detector")
        self.setGeometry(100, 100, 1200, 800)
        
        self.setup_menu()
        self.setup_ui()
    
    def setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        file_menu = menubar.addMenu('File')
        
        # Load List action
        load_action = QAction('Load List', self)
        load_action.triggered.connect(self.load_file_list)
        file_menu.addAction(load_action)
        
        file_menu.addSeparator()
        
        # Analyze Colors action
        analyze_action = QAction('Analyze Colors', self)
        analyze_action.triggered.connect(self.analyze_colors)
        analyze_action.setEnabled(False)  # Disabled until images are loaded
        file_menu.addAction(analyze_action)
        self.analyze_action = analyze_action  # Store reference for enabling/disabling
        
        # Convert action
        convert_action = QAction('Convert', self)
        convert_action.triggered.connect(self.convert_selected)
        file_menu.addAction(convert_action)

        file_menu.addSeparator()

        # Export action
        export_action = QAction('Export', self)
        export_action.triggered.connect(self.export_documents)
        export_action.setEnabled(False)
        file_menu.addAction(export_action)
        self.export_action = export_action
    
    def setup_ui(self):
        """Setup main UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout
        main_layout = QHBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Left panel - Thumbnail grid
        self.setup_thumbnail_panel(main_layout)
        
        # Right panel - Large image view
        self.setup_image_view_panel(main_layout)
    
    def setup_thumbnail_panel(self, parent_layout):
        """Setup left panel with thumbnail grid"""
        # Container for thumbnails
        thumbnail_container = QFrame()
        thumbnail_container.setFrameStyle(QFrame.Shape.StyledPanel)
        thumbnail_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout()
        thumbnail_container.setLayout(layout)
        
        # Scroll area for thumbnails
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Grid widget for thumbnails
        self.thumbnail_grid = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(2)
        self.thumbnail_grid.setLayout(self.grid_layout)
        
        self.scroll_area.setWidget(self.thumbnail_grid)
        layout.addWidget(self.scroll_area)
        
        parent_layout.addWidget(thumbnail_container, 2)
        
        # Ensure initial sizing is applied after layout is ready
        self.update_thumbnail_cell_sizes()
    
    def setup_image_view_panel(self, parent_layout):
        """Setup right panel for large image view"""
        # Container for large image
        image_container = QFrame()
        image_container.setFrameStyle(QFrame.Shape.StyledPanel)
        
        layout = QVBoxLayout()
        image_container.setLayout(layout)
        
        # Large image label
        self.large_image_label = QLabel("Select an image to view")
        self.large_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.large_image_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.large_image_label.setMinimumSize(400, 500)
        self.large_image_label.setScaledContents(False)
        
        layout.addWidget(self.large_image_label)
        
        parent_layout.addWidget(image_container, 1)
    
    def load_file_list(self):
        """Load CSV file with document structure"""
        selected_path, _ = QFileDialog.getOpenFileName(
            self, "Load Document List", "", "Text Files (*.txt *.csv);;All Files (*)"
        )
        
        if selected_path:
            try:
                self.document_data = []
                self.image_files = []
                base_dir = os.path.dirname(selected_path)
                
                with open(selected_path, 'r', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        if len(row) > 1:  # Skip empty rows
                            self.document_data.append(row)
                            
                            # Extract JPG files (skip .tif files as per requirements)
                            for i in range(1, len(row)):
                                image_name = row[i].strip()
                                if image_name.lower().endswith('.jpg'):
                                    # Resolve relative paths against the source file's directory
                                    image_path = image_name if os.path.isabs(image_name) else os.path.join(base_dir, image_name)
                                    self.image_files.append(image_path)
                
                self.file_path = selected_path  # Store for later updating
                self.populate_thumbnails()
                
                # Enable the analyze action now that we have images
                self.analyze_action.setEnabled(len(self.image_files) > 0)

                # Enable export now that a list is loaded
                if hasattr(self, 'export_action'):
                    self.export_action.setEnabled(True)
                
                QMessageBox.information(self, "Success", f"Loaded {len(self.image_files)} JPG files from {len(self.document_data)} documents")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def export_documents(self):
        """Export multipage TIFF and PDF files based on the loaded import file."""
        if not hasattr(self, 'file_path') or not self.file_path:
            QMessageBox.information(self, "No List", "Please load an import list first")
            return

        try:
            self.setWindowTitle("Monochrome Detector - Exporting...")
            num_tiffs, num_pdfs = export_from_import_file(self.file_path)
            self.setWindowTitle("Monochrome Detector")
            QMessageBox.information(self, "Export Complete", f"Created {num_tiffs} TIFF(s) and {num_pdfs} PDF(s)")
        except Exception as e:
            self.setWindowTitle("Monochrome Detector")
            QMessageBox.critical(self, "Export Failed", str(e))
    
    def populate_thumbnails(self):
        """Populate thumbnail grid with images"""
        # Clear existing thumbnails
        for widget in self.thumbnail_widgets:
            widget.deleteLater()
        self.thumbnail_widgets.clear()
        # Clear selected images set
        self.selected_images.clear()
        
        # Create thumbnails in 6 column grid
        cols = 6
        for i, image_path in enumerate(self.image_files):
            row = i // cols
            col = i % cols
            
            filename = os.path.basename(image_path)
            thumbnail = ThumbnailWidget(image_path, filename)
            thumbnail.clicked.connect(self.on_thumbnail_clicked)
            
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)
        
        # Apply responsive sizing to match current panel width
        self.update_thumbnail_cell_sizes()

        # Update analyze action state
        if hasattr(self, 'analyze_action'):
            self.analyze_action.setEnabled(len(self.image_files) > 0)

    def update_thumbnail_cell_sizes(self):
        """Resize thumbnail cells to 15% of the thumbnail panel width (square)."""
        try:
            if not hasattr(self, 'scroll_area'):
                return
            panel_width = self.scroll_area.viewport().width()
            if panel_width <= 0:
                return
            # 15% of panel width per cell; account for small spacing
            target_size = int(max(60, panel_width * 0.15))
            for widget in self.thumbnail_widgets:
                widget.set_cell_size(target_size)
        except Exception:
            pass

    def resizeEvent(self, event):
        """Handle window resizing to keep thumbnails responsive."""
        super().resizeEvent(event)
        self.update_thumbnail_cell_sizes()
    
    def on_thumbnail_clicked(self, image_path):
        """Handle thumbnail click"""
        # Find the widget that was clicked
        clicked_widget = None
        for widget in self.thumbnail_widgets:
            if widget.image_path == image_path:
                clicked_widget = widget
                break
        
        if clicked_widget:
            # Update selected_images set based on checkbox state
            if clicked_widget.is_checked():
                self.selected_images.add(image_path)
            else:
                self.selected_images.discard(image_path)
        
        self.show_large_image(image_path)
    
    def show_large_image(self, image_path):
        """Display large image in right panel"""
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                # Scale to fit the label while maintaining aspect ratio
                label_size = self.large_image_label.size()
                scaled_pixmap = pixmap.scaled(
                    label_size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.large_image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Error loading large image {image_path}: {e}")
    
    def analyze_colors(self):
        """Analyze all loaded images to detect monochrome candidates"""
        if not self.image_files:
            QMessageBox.information(self, "No Images", "Please load images first")
            return

        # Disable the analyze action during analysis
        self.analyze_action.setEnabled(False)
        
        # Start color analysis in separate thread
        self.color_analysis_thread = ColorAnalysisThread(self.image_files)
        self.color_analysis_thread.progress.connect(self.show_progress)
        self.color_analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.color_analysis_thread.start()
    
    def on_analysis_complete(self, monochrome_candidates: List[str]):
        """Handle completion of color analysis"""
        try:
            # Re-enable the analyze action
            self.analyze_action.setEnabled(True)
            
            # Reset window title
            self.setWindowTitle("Monochrome Detector")
            
            # Auto-check boxes for monochrome candidates
            checked_count = 0
            for widget in self.thumbnail_widgets:
                if widget.image_path in monochrome_candidates:
                    widget.checkbox.setChecked(True)
                    self.selected_images.add(widget.image_path)
                    checked_count += 1
            
            # Show results
            QMessageBox.information(
                self, 
                "Analysis Complete", 
                f"Found {len(monochrome_candidates)} monochrome candidates out of {len(self.image_files)} images.\n"
                f"Auto-checked {checked_count} thumbnails for conversion."
            )
            
        except Exception as e:
            self.analyze_action.setEnabled(True)
            self.setWindowTitle("Monochrome Detector")
            QMessageBox.critical(self, "Error", f"Failed to complete analysis: {str(e)}")
    
    def convert_selected(self):
        """Convert selected images to G4 TIFF"""
        selected_paths = []
        for widget in self.thumbnail_widgets:
            if widget.is_checked():
                selected_paths.append(widget.image_path)
        
        print(f"Selected {len(selected_paths)} images for conversion:")
        for path in selected_paths:
            print(f"  - {os.path.basename(path)}")
        
        if not selected_paths:
            QMessageBox.information(self, "No Selection", "Please select images to convert")
            return
        
        # Start conversion in separate thread
        self.converter_thread = ImageConverter(selected_paths)
        self.converter_thread.progress.connect(self.show_progress)
        self.converter_thread.finished.connect(self.on_conversion_finished)
        self.converter_thread.start()
    
    def show_progress(self, message):
        """Show conversion progress"""
        print(message)  # Print to console for debugging
        # Update window title to show progress
        self.setWindowTitle(f"Monochrome Detector - {message}")
    
    def on_conversion_finished(self, converted_files):
        """Handle conversion completion"""
        try:
            # Reset window title
            self.setWindowTitle("Monochrome Detector")
            
            # Update source file with new .tif filenames
            self.update_source_file(converted_files)
            
            # Remove converted items from grid
            self.remove_converted_items(converted_files)
            
            QMessageBox.information(self, "Success", f"Converted {len(converted_files)} images to G4 TIFF")
            
        except Exception as e:
            self.setWindowTitle("Monochrome Detector")
            QMessageBox.critical(self, "Error", f"Failed to update files: {str(e)}")
    
    def update_source_file(self, converted_files):
        """Update the source CSV file with new .tif filenames"""
        # Create mapping of old to new filenames
        filename_mapping = {}
        for old_path, new_path in converted_files:
            old_filename = os.path.basename(old_path)
            new_filename = os.path.basename(new_path)
            filename_mapping[old_filename] = new_filename
        
        # Update document data
        for row in self.document_data:
            for i in range(1, len(row)):
                filename = row[i].strip()
                if filename in filename_mapping:
                    row[i] = filename_mapping[filename]
        
        # Write updated data back to file
        with open(self.file_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(self.document_data)
    
    def remove_converted_items(self, converted_files):
        """Remove converted items from thumbnail grid"""
        converted_paths = {old_path for old_path, _ in converted_files}
        
        # Remove from image_files list
        self.image_files = [path for path in self.image_files if path not in converted_paths]
        
        # Repopulate thumbnails
        self.populate_thumbnails()


def main():
    app = QApplication(sys.argv)
    window = MonochromeDetector()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

