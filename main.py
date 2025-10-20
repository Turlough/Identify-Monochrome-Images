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
                            QFrame, QSizePolicy, QPushButton, QListWidget, QListWidgetItem,
                            QProgressDialog)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QAction, QFont, QCursor, QColor
from color_detector import ColorDetector
from exporter import export_from_import_file
from thumbnails import ThumbnailWidget

from color_analyser import ColorAnalysisThread
from image_converter import ImageConverter
from dotenv import load_dotenv
from thumbnail_loader import ThumbnailLoader

class MonochromeDetector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document_data = []
        self.image_files = []
        self.thumbnail_widgets = []
        self.selected_images = set()
        self.converter_thread = None
        self.color_analysis_thread = None
        self.current_document_index = 0
        self.pending_navigation_index = None
        self.is_converting = False
        
        self.setWindowTitle("Monochrome Detector")
        self.setGeometry(100, 100, 1200, 800)
        
        self.setup_menu()
        self.setup_ui()
        
        # Async thumbnail loader and mapping
        max_threads = max(2, (os.cpu_count() or 4) // 2)
        self.thumbnail_loader = ThumbnailLoader(max_threads=max_threads)
        self.thumbnail_loader.thumbnailReady.connect(self._on_thumb_ready)
        self.thumbnail_loader.thumbnailFailed.connect(self._on_thumb_failed)
        self._path_to_widget: Dict[str, ThumbnailWidget] = {}
    
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
        
        # Left panel - Document list
        self.setup_document_list_panel(main_layout)
        
        # Middle panel - Thumbnail grid
        self.setup_thumbnail_panel(main_layout)
        
        # Right panel - Large image view
        self.setup_image_view_panel(main_layout)
    
    def setup_document_list_panel(self, parent_layout):
        """Setup left panel with document list"""
        # Container for document list
        doc_list_container = QFrame()
        doc_list_container.setFrameStyle(QFrame.Shape.StyledPanel)
        doc_list_container.setMinimumWidth(250)
        doc_list_container.setMaximumWidth(320)
        
        layout = QVBoxLayout()
        doc_list_container.setLayout(layout)
        
        # Label
        list_label = QLabel("Documents")
        font = QFont()
        font.setBold(True)
        list_label.setFont(font)
        list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(list_label)
        
        # Document list widget
        self.document_list_widget = QListWidget()
        self.document_list_widget.itemClicked.connect(self.on_document_list_item_clicked)
        layout.addWidget(self.document_list_widget)
        
        parent_layout.addWidget(doc_list_container)
    
    def setup_thumbnail_panel(self, parent_layout):
        """Setup left panel with thumbnail grid"""
        # Container for thumbnails
        thumbnail_container = QFrame()
        thumbnail_container.setFrameStyle(QFrame.Shape.StyledPanel)
        thumbnail_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        layout = QVBoxLayout()
        thumbnail_container.setLayout(layout)
        
        # Navigation bar
        nav_layout = QHBoxLayout()
        
        # Previous button
        self.prev_button = QPushButton("◀ Previous")
        self.prev_button.setMinimumHeight(40)
        self.prev_button.clicked.connect(self.show_previous_document)
        self.prev_button.setEnabled(False)
        nav_layout.addWidget(self.prev_button)
        
        # Next button
        self.next_button = QPushButton("Next ▶")
        self.next_button.setMinimumHeight(40)
        self.next_button.clicked.connect(self.show_next_document)
        self.next_button.setEnabled(False)
        nav_layout.addWidget(self.next_button)
        
        # Document info label
        self.doc_info_label = QLabel("No document loaded")
        self.doc_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setBold(True)
        self.doc_info_label.setFont(font)
        nav_layout.addWidget(self.doc_info_label, 1)
        
        layout.addLayout(nav_layout)
        
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
        load_dotenv()
        default_folder = os.getenv('DEFAULT_PICKER_FOLDER')
        selected_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Document List", 
            default_folder,
            "Text Files (*.txt *.csv);;All Files (*)"
        )
        
        if selected_path:
            try:
                self.show_busy_cursor(True)
                
                self.document_data = []
                base_dir = os.path.dirname(selected_path)
                
                with open(selected_path, 'r', encoding='utf-8') as file:
                    reader = csv.reader(file)
                    for row in reader:
                        if len(row) > 1:  # Skip empty rows
                            self.document_data.append(row)
                
                self.file_path = selected_path  # Store for later updating
                self.base_dir = base_dir  # Store base directory for resolving paths
                
                # Populate document list
                self.populate_document_list()
                
                # Start with first document
                self.current_document_index = 0
                self.show_current_document()
                
                # Update navigation buttons
                self.update_navigation_buttons()

                # Enable export now that a list is loaded
                if hasattr(self, 'export_action'):
                    self.export_action.setEnabled(True)
                
                self.show_busy_cursor(False)
                QMessageBox.information(self, "Success", f"Loaded {len(self.document_data)} documents")
                
            except Exception as e:
                self.show_busy_cursor(False)
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def populate_document_list(self):
        """Populate the document list widget"""
        self.document_list_widget.clear()
        for idx, row in enumerate(self.document_data):
            doc_name = row[0] if row else "Unknown"
            
            # Count JPG files (color) and total files (starting from index 2, first two are metadata)
            jpg_count = 0
            total_count = 0
            for i in range(2, len(row)):
                filename = row[i].strip()
                if filename:  # Skip empty entries
                    # Only count .jpg and .tif files
                    if filename.lower().endswith('.jpg'):
                        jpg_count += 1
                        total_count += 1
                    elif filename.lower().endswith('.tif'):
                        total_count += 1
            
            # Calculate percentage of color pages
            if total_count > 0:
                color_percentage = round((jpg_count / total_count) * 100)
                stats_text = f"{jpg_count}/{total_count} ({color_percentage}%) colour"
            else:
                stats_text = "0/0 (0%) colour"
                color_percentage = 0
            
            # Format: 4-digit index, document name, and statistics
            item_text = f"{idx + 1:04d} {doc_name} - {stats_text}"
            item = QListWidgetItem(item_text)
            
            # Highlight fully-color documents in red
            if color_percentage == 100 and total_count > 0:
                item.setForeground(QColor(Qt.GlobalColor.red))
            
            self.document_list_widget.addItem(item)
    
    def on_document_list_item_clicked(self, item):
        """Handle click on document list item"""
        # Extract the index from the clicked item (first 4 digits)
        clicked_index = self.document_list_widget.row(item)
        if clicked_index >= 0 and clicked_index < len(self.document_data):
            # Navigate to the selected document (with auto-conversion)
            self.navigate_to_document(clicked_index)
    
    def navigate_to_document(self, target_index):
        """Navigate to a document, converting selected images first if needed"""
        if target_index == self.current_document_index:
            return
        
        # Check if there are selected images to convert
        selected_paths = self.get_selected_images()
        
        if selected_paths and not self.is_converting:
            # Store the target index for after conversion
            self.pending_navigation_index = target_index
            # Convert selected images (will show busy cursor)
            self.convert_selected_for_navigation()
        else:
            # No conversion needed, navigate directly
            self.show_busy_cursor(True)
            self.current_document_index = target_index
            self.show_current_document()
            self.update_navigation_buttons()
            self.show_busy_cursor(False)
    
    def get_selected_images(self):
        """Get list of currently selected image paths"""
        selected_paths = []
        for widget in self.thumbnail_widgets:
            if widget.is_checked():
                selected_paths.append(widget.image_path)
        return selected_paths
    
    def convert_selected_for_navigation(self):
        """Convert selected images before navigation"""
        selected_paths = self.get_selected_images()
        if not selected_paths:
            return
        
        # Check if any selected image is the first JPG in the current document
        first_jpg_path = self.get_first_jpg_in_current_document()
        if first_jpg_path and first_jpg_path in selected_paths:
            QMessageBox.warning(
                self,
                "Cannot Convert First Page",
                "The first JPG in each document cannot be selected for conversion.\n\n"
                "Rationale: The multipage TIFF will be entirely G4 if the first page is G4."
            )
            return
        
        self.is_converting = True
        self.show_busy_cursor(True)
        
        # Start conversion in separate thread
        self.converter_thread = ImageConverter(selected_paths)
        self.converter_thread.progress.connect(self.show_progress)
        self.converter_thread.finished.connect(self.on_navigation_conversion_finished)
        self.converter_thread.start()
    
    def on_navigation_conversion_finished(self, converted_files):
        """Handle conversion completion when triggered by navigation"""
        try:
            self.is_converting = False
            
            # Update source file with new .tif filenames
            if converted_files:
                self.update_source_file(converted_files)
                # Refresh document list to show updated statistics
                self.populate_document_list()
            
            # Now navigate to the pending document
            if self.pending_navigation_index is not None:
                self.current_document_index = self.pending_navigation_index
                self.pending_navigation_index = None
                self.show_current_document()
                self.update_navigation_buttons()
            
            self.show_busy_cursor(False)
            
        except Exception as e:
            self.is_converting = False
            self.show_busy_cursor(False)
            QMessageBox.critical(self, "Error", f"Failed to convert images: {str(e)}")
    
    def get_first_jpg_in_current_document(self):
        """Get the path to the first JPG file in the current document"""
        if not self.document_data or self.current_document_index >= len(self.document_data):
            return None
        
        current_row = self.document_data[self.current_document_index]
        
        # Find the first JPG file (starting from index 2, first two are metadata)
        for i in range(2, len(current_row)):
            image_name = current_row[i].strip()
            if image_name.lower().endswith('.jpg'):
                # Resolve relative paths against the source file's directory
                image_path = image_name if os.path.isabs(image_name) else os.path.join(self.base_dir, image_name)
                return image_path
        
        return None

    def show_current_document(self):
        """Display thumbnails for the current document"""
        if not self.document_data:
            return
        
        # Get images for current document
        self.image_files = []
        current_row = self.document_data[self.current_document_index]
        
        # Extract JPG files from current document row (starting from index 2, first two are metadata)
        for i in range(2, len(current_row)):
            image_name = current_row[i].strip()
            if image_name.lower().endswith('.jpg'):
                # Resolve relative paths against the source file's directory
                image_path = image_name if os.path.isabs(image_name) else os.path.join(self.base_dir, image_name)
                self.image_files.append(image_path)
        
        # Update document info label
        doc_name = current_row[0] if current_row else "Unknown"
        self.doc_info_label.setText(f"Document {self.current_document_index + 1} of {len(self.document_data)}: {doc_name}")
        
        # Update selection in document list
        self.document_list_widget.setCurrentRow(self.current_document_index)
        
        # Populate thumbnails for this document
        self.populate_thumbnails()
        
        # Enable the analyze action if we have images
        if hasattr(self, 'analyze_action'):
            self.analyze_action.setEnabled(len(self.image_files) > 0)
    
    def show_previous_document(self):
        """Navigate to previous document"""
        if self.current_document_index > 0:
            self.navigate_to_document(self.current_document_index - 1)
    
    def show_next_document(self):
        """Navigate to next document"""
        if self.current_document_index < len(self.document_data) - 1:
            self.navigate_to_document(self.current_document_index + 1)
    
    def update_navigation_buttons(self):
        """Update the enabled state of navigation buttons"""
        if not self.document_data:
            self.prev_button.setEnabled(False)
            self.next_button.setEnabled(False)
            return
        
        self.prev_button.setEnabled(self.current_document_index > 0)
        self.next_button.setEnabled(self.current_document_index < len(self.document_data) - 1)
    
    def show_busy_cursor(self, show=True):
        """Show or hide busy cursor"""
        if show:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    def export_documents(self):
        """Export multipage TIFF and PDF files based on the loaded import file."""
        if not hasattr(self, 'file_path') or not self.file_path:
            QMessageBox.information(self, "No List", "Please load an import list first")
            return

        try:
            self.show_busy_cursor(True)
            self.setWindowTitle("Monochrome Detector - Exporting...")
            num_tiffs, num_pdfs = export_from_import_file(self.file_path)
            self.show_busy_cursor(False)
            self.setWindowTitle("Monochrome Detector")
            QMessageBox.information(self, "Export Complete", f"Created {num_tiffs} TIFF(s) and {num_pdfs} PDF(s)")
        except Exception as e:
            self.show_busy_cursor(False)
            self.setWindowTitle("Monochrome Detector")
            QMessageBox.critical(self, "Export Failed", str(e))
    
    def populate_thumbnails(self):
        """Populate thumbnail grid with images"""
        # Indicate progress in the window title
        try:
            total_images = len(self.image_files)
            if total_images > 0:
                self.setWindowTitle("Monochrome Detector - Loading thumbnails...")
        except Exception:
            pass
        # Clear existing thumbnails
        for widget in self.thumbnail_widgets:
            widget.deleteLater()
        self.thumbnail_widgets.clear()
        # Clear selected images set
        self.selected_images.clear()
        # Clear mapping for old widgets
        self._path_to_widget.clear()
        
        # Get the first JPG in current document for validation
        first_jpg_path = self.get_first_jpg_in_current_document()
        
        # Create thumbnails in 6 column grid
        cols = 6
        for i, image_path in enumerate(self.image_files):
            row = i // cols
            col = i % cols
            
            filename = os.path.basename(image_path)
            # Check if this is the first JPG in the document
            is_first_jpg = (image_path == first_jpg_path)
            thumbnail = ThumbnailWidget(image_path, filename, is_first_jpg)
            thumbnail.clicked.connect(self.on_thumbnail_clicked)
            
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)
            self._path_to_widget[image_path] = thumbnail
            
            # Queue async thumbnail load sized to the image area
            cell = thumbnail._cell_size
            target = QSize(max(10, cell - 4), max(10, cell - 24))
            self.thumbnail_loader.request(image_path, target)
            
            # Update progress in the title bar and keep UI responsive
            try:
                if (i + 1) % 5 == 0 or (i + 1) == len(self.image_files):
                    self.setWindowTitle(f"Monochrome Detector - Loading thumbnails {i + 1}/{len(self.image_files)}")
                    QApplication.processEvents()
            except Exception:
                pass
        
        # Apply responsive sizing to match current panel width
        self.update_thumbnail_cell_sizes()

        # Update analyze action state
        if hasattr(self, 'analyze_action'):
            self.analyze_action.setEnabled(len(self.image_files) > 0)
        
        # Reset title after loading
        try:
            self.setWindowTitle("Monochrome Detector")
        except Exception:
            pass

    def _on_thumb_ready(self, path: str, image):
        widget = self._path_to_widget.get(path)
        if widget is not None:
            widget.set_thumbnail(image)

    def _on_thumb_failed(self, path: str, message: str):
        # For now, we silently ignore or could set a placeholder
        print(f"Failed to load thumbnail for {os.path.basename(path)}: {message}")

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
        self.show_busy_cursor(True)
        
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
            self.show_busy_cursor(False)
            
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
            self.show_busy_cursor(False)
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
        
        # Check if any selected image is the first JPG in the current document
        first_jpg_path = self.get_first_jpg_in_current_document()
        if first_jpg_path and first_jpg_path in selected_paths:
            QMessageBox.warning(
                self,
                "Cannot Convert First Page",
                "The first JPG in each document cannot be selected for conversion.\n\n"
                "Rationale: The multipage TIFF will be entirely G4 if the first page is G4."
            )
            return
        
        self.show_busy_cursor(True)
        
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
            self.show_busy_cursor(False)
            
            # Reset window title
            self.setWindowTitle("Monochrome Detector")
            
            # Update source file with new .tif filenames
            self.update_source_file(converted_files)
            
            # Refresh document list to show updated statistics
            self.populate_document_list()
            
            # Remove converted items from grid
            self.remove_converted_items(converted_files)
            
            QMessageBox.information(self, "Success", f"Converted {len(converted_files)} images to G4 TIFF")
            
        except Exception as e:
            self.show_busy_cursor(False)
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
        
        # Update document data (starting from index 2, first two are metadata)
        for row in self.document_data:
            for i in range(2, len(row)):
                filename = row[i].strip()
                if filename in filename_mapping:
                    row[i] = filename_mapping[filename]
        
        # Write updated data back to file
        with open(self.file_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerows(self.document_data)
    
    def remove_converted_items(self, converted_files):
        """Remove converted items from thumbnail grid"""
        # Refresh the current document view to show updated filenames
        self.show_current_document()
        self.update_navigation_buttons()


def main():
    app = QApplication(sys.argv)
    window = MonochromeDetector()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


