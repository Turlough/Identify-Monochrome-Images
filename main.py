import sys
import os
import csv
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Dict, Tuple
from PIL import Image, ImageOps
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QScrollArea, QLabel, 
                            QCheckBox, QMenuBar, QFileDialog, QMessageBox,
                            QFrame, QSizePolicy, QPushButton, QListWidget, QListWidgetItem,
                            QProgressDialog, QDialog, QProgressBar)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QTimer, QRect, QPoint
from PyQt6.QtGui import QPixmap, QAction, QFont, QCursor, QColor, QPainter, QPen
from color_detector import ColorDetector
from exporter import export_from_import_file, export_from_import_file_concurrent
from thumbnails import ThumbnailWidget

from color_analyser import ColorAnalysisThread
from image_converter import ImageConverter, convert_image_to_g4_tiff
from dotenv import load_dotenv
from thumbnail_loader import ThumbnailLoader


class ImageViewWidget(QLabel):
    """Custom widget for displaying images with selection rectangle drawing capability"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        self.setMinimumSize(400, 500)
        self.setScaledContents(False)
        
        # Selection rectangle state
        self.selection_start = None
        self.selection_end = None
        self.is_drawing = False
        self.selection_rect = None
        
        # Enable mouse tracking for drawing
        self.setMouseTracking(True)
    
    def mousePressEvent(self, event):
        """Handle mouse press to start selection"""
        if event.button() == Qt.MouseButton.LeftButton:
            # Constrain start point to image bounds
            constrained_pos = self._constrain_to_image_bounds(event.pos())
            if constrained_pos:
                self.selection_start = constrained_pos
                self.selection_end = constrained_pos
                self.is_drawing = True
                self.selection_rect = None
    
    def mouseMoveEvent(self, event):
        """Handle mouse move to update selection"""
        if self.is_drawing:
            # Constrain end point to image bounds
            constrained_pos = self._constrain_to_image_bounds(event.pos())
            if constrained_pos:
                self.selection_end = constrained_pos
                self.update()  # Trigger repaint
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release to finish selection"""
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            # Constrain end point to image bounds
            constrained_pos = self._constrain_to_image_bounds(event.pos())
            if constrained_pos:
                self.selection_end = constrained_pos
            self.is_drawing = False
            
            # Create normalized selection rectangle
            if self.selection_start and self.selection_end:
                # Ensure start is before end (normalize the rectangle)
                start_x = min(self.selection_start.x(), self.selection_end.x())
                start_y = min(self.selection_start.y(), self.selection_end.y())
                end_x = max(self.selection_start.x(), self.selection_end.x())
                end_y = max(self.selection_start.y(), self.selection_end.y())
                
                self.selection_start = QPoint(start_x, start_y)
                self.selection_end = QPoint(end_x, end_y)
                
                self.selection_rect = self._normalize_selection()
    
    def paintEvent(self, event):
        """Custom paint event to draw selection rectangle"""
        super().paintEvent(event)
        
        if self.is_drawing and self.selection_start and self.selection_end:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.SolidLine))
            
            # Draw selection rectangle
            rect = QRect(self.selection_start, self.selection_end).normalized()
            painter.drawRect(rect)
    
    def _normalize_selection(self):
        """Convert selection coordinates to normalized values (0-1) based on image size"""
        if not self.selection_start or not self.selection_end:
            return None
        
        # Get the actual image size within the label
        pixmap = self.pixmap()
        if pixmap.isNull():
            return None
        
        # Calculate the displayed image size and position
        label_size = self.size()
        pixmap_size = pixmap.size()
        
        # Calculate scaling to fit the label while maintaining aspect ratio
        scale_x = label_size.width() / pixmap_size.width()
        scale_y = label_size.height() / pixmap_size.height()
        scale = min(scale_x, scale_y)
        
        # Calculate the actual displayed image size
        displayed_width = int(pixmap_size.width() * scale)
        displayed_height = int(pixmap_size.height() * scale)
        
        # Calculate the offset to center the image
        offset_x = (label_size.width() - displayed_width) // 2
        offset_y = (label_size.height() - displayed_height) // 2
        
        # Convert selection coordinates to image coordinates
        start_x = max(0, (self.selection_start.x() - offset_x) / scale)
        start_y = max(0, (self.selection_start.y() - offset_y) / scale)
        end_x = min(pixmap_size.width(), (self.selection_end.x() - offset_x) / scale)
        end_y = min(pixmap_size.height(), (self.selection_end.y() - offset_y) / scale)
        
        # Ensure valid rectangle with minimum size
        if start_x >= end_x or start_y >= end_y:
            return None
        
        # Check for minimum selection size (at least 10x10 pixels)
        if (end_x - start_x) < 10 or (end_y - start_y) < 10:
            return None
        
        # Return normalized coordinates (0-1)
        return {
            'x': start_x / pixmap_size.width(),
            'y': start_y / pixmap_size.height(),
            'width': (end_x - start_x) / pixmap_size.width(),
            'height': (end_y - start_y) / pixmap_size.height()
        }
    
    def _constrain_to_image_bounds(self, pos):
        """Constrain a point to the actual image bounds within the widget"""
        pixmap = self.pixmap()
        if pixmap.isNull():
            return None
        
        # Calculate the displayed image size and position
        label_size = self.size()
        pixmap_size = pixmap.size()
        
        # Calculate scaling to fit the label while maintaining aspect ratio
        scale_x = label_size.width() / pixmap_size.width()
        scale_y = label_size.height() / pixmap_size.height()
        scale = min(scale_x, scale_y)
        
        # Calculate the actual displayed image size
        displayed_width = int(pixmap_size.width() * scale)
        displayed_height = int(pixmap_size.height() * scale)
        
        # Calculate the offset to center the image
        offset_x = (label_size.width() - displayed_width) // 2
        offset_y = (label_size.height() - displayed_height) // 2
        
        # Constrain the point to the image bounds
        constrained_x = max(offset_x, min(offset_x + displayed_width, pos.x()))
        constrained_y = max(offset_y, min(offset_y + displayed_height, pos.y()))
        
        return QPoint(constrained_x, constrained_y)
    
    def clear_selection(self):
        """Clear the current selection"""
        self.selection_start = None
        self.selection_end = None
        self.selection_rect = None
        self.is_drawing = False
        self.update()


class ExportProgressDialog(QDialog):
    """Progress dialog for concurrent export with time estimates."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Exporting Documents...")
        self.setModal(True)
        self.setFixedSize(400, 200)
        
        # Time tracking
        self.start_time = time.time()
        self.last_update_time = self.start_time
        
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Preparing export...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)
        
        # Time estimates
        self.time_label = QLabel("")
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.time_label)
        
        # Current document label
        self.current_doc_label = QLabel("")
        self.current_doc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.current_doc_label.setWordWrap(True)
        layout.addWidget(self.current_doc_label)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        layout.addWidget(self.cancel_button)
        
    def update_progress(self, completed, total, doc_name, tiff_success, pdf_success):
        """Update progress with time estimates."""
        current_time = time.time()
        elapsed = current_time - self.start_time
        
        # Update progress bar
        progress = int((completed / total) * 100) if total > 0 else 0
        self.progress_bar.setValue(progress)
        
        # Update status
        self.status_label.setText(f"Exported {completed} of {total} documents")
        
        # Update current document
        status_icons = []
        if tiff_success:
            status_icons.append("✓ TIFF")
        if pdf_success:
            status_icons.append("✓ PDF")
        
        status_text = f"Completed: {doc_name}"
        if status_icons:
            status_text += f" ({', '.join(status_icons)})"
        
        self.current_doc_label.setText(status_text)
        
        # Calculate time estimates
        if completed > 0:
            avg_time_per_doc = elapsed / completed
            remaining_docs = total - completed
            estimated_remaining = avg_time_per_doc * remaining_docs
            estimated_total = elapsed + estimated_remaining
            
            # Format time strings
            elapsed_str = self._format_time(elapsed)
            remaining_str = self._format_time(estimated_remaining)
            total_str = self._format_time(estimated_total)
            
            self.time_label.setText(f"Elapsed: {elapsed_str} | Remaining: {remaining_str} | Total: {total_str}")
        
        # Force UI update
        QApplication.processEvents()
        
    def _format_time(self, seconds):
        """Format time in MM:SS or HH:MM:SS format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes:02d}:{secs:02d}"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            secs = int(seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class ExportThread(QThread):
    """Thread for concurrent export processing."""
    
    progress = pyqtSignal(int, int, str, bool, bool)  # completed, total, doc_name, tiff_success, pdf_success
    finished = pyqtSignal(int, int)  # num_tiffs, num_pdfs
    
    def __init__(self, import_file):
        super().__init__()
        self.import_file = import_file
        
    def run(self):
        """Run the concurrent export."""
        try:
            num_tiffs, num_pdfs = export_from_import_file_concurrent(
                self.import_file, 
                self.progress_callback
            )
            self.finished.emit(num_tiffs, num_pdfs)
        except Exception as e:
            logging.error(f"Export failed: {e}")
            self.finished.emit(0, 0)
    
    def progress_callback(self, completed, total, doc_name, tiff_success, pdf_success):
        """Callback for progress updates."""
        self.progress.emit(completed, total, doc_name, tiff_success, pdf_success)


class MonochromeDetector(QMainWindow):
    def __init__(self):
        super().__init__()
        # Load environment variables
        load_dotenv()
        self.num_data_columns = int(os.getenv('NUM_DATA_COLUMNS', '2'))
        self.filename_column = int(os.getenv('FILENAME_COLUMN', '1'))
        
        self.document_data = []
        self.image_files = []
        self.thumbnail_widgets = []
        self.selected_images = set()
        self.converter_thread = None
        self.color_analysis_thread = None
        self.export_thread = None
        self.export_progress_dialog = None
        self.current_document_index = 0
        self.pending_navigation_index = None
        self.is_converting = False
        
        # Store current displayed image path and whether we're showing TIFF
        self.current_displayed_image = None
        self.is_showing_tiff = False
        
        # Rotation state for the currently displayed image
        self.current_rotation = 0
        
        # Crop state for the currently displayed image
        self.current_crop_rect = None
        
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
        
        # Clone Previous pattern action
        clone_prev_action = QAction('Clone Previous', self)
        clone_prev_action.triggered.connect(self.clone_previous_pattern)
        clone_prev_action.setEnabled(False)  # Enabled when a previous doc exists
        file_menu.addAction(clone_prev_action)
        self.clone_previous_action = clone_prev_action
        
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
        
        # Detect button
        self.detect_button = QPushButton("🔍 Detect")
        self.detect_button.setMinimumHeight(40)
        self.detect_button.setEnabled(False)
        self.detect_button.clicked.connect(self.analyze_colors)
        nav_layout.addWidget(self.detect_button)
        
        # Peek B&W button
        self.peek_bw_button = QPushButton("👁️ Peek")
        self.peek_bw_button.setMinimumHeight(40)
        self.peek_bw_button.setEnabled(False)
        self.peek_bw_button.pressed.connect(self.on_peek_bw_pressed)
        self.peek_bw_button.released.connect(self.on_peek_bw_released)
        nav_layout.addWidget(self.peek_bw_button)
        
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
        
        # Control buttons layout
        button_layout = QHBoxLayout()
        
        # Rotate left button
        self.rotate_left_button = QPushButton("↺ Rotate Left")
        self.rotate_left_button.setMinimumHeight(40)
        self.rotate_left_button.setEnabled(False)
        self.rotate_left_button.clicked.connect(self.rotate_left)
        button_layout.addWidget(self.rotate_left_button)
        
        # Rotate right button
        self.rotate_right_button = QPushButton("↻ Rotate Right")
        self.rotate_right_button.setMinimumHeight(40)
        self.rotate_right_button.setEnabled(False)
        self.rotate_right_button.clicked.connect(self.rotate_right)
        button_layout.addWidget(self.rotate_right_button)
        
        # Crop button
        self.crop_button = QPushButton("✂️ Crop")
        self.crop_button.setMinimumHeight(40)
        self.crop_button.setEnabled(False)
        self.crop_button.clicked.connect(self.crop_image)
        button_layout.addWidget(self.crop_button)
        
        # Save button
        self.save_rotation_button = QPushButton("💾 Save")
        self.save_rotation_button.setMinimumHeight(40)
        self.save_rotation_button.setEnabled(False)
        self.save_rotation_button.clicked.connect(self.save_rotation)
        button_layout.addWidget(self.save_rotation_button)
        
        layout.addLayout(button_layout)
        
        # Large image widget with selection capability
        self.large_image_label = ImageViewWidget()
        self.large_image_label.setText("Select an image to view")
        
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
                
                # Update window title to show the import file path
                self.setWindowTitle(f"Monochrome Detector - {selected_path}")
                QApplication.processEvents()  # Force immediate UI update
                
                self.show_busy_cursor(False)
                
            except Exception as e:
                self.show_busy_cursor(False)
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def populate_document_list(self):
        """Populate the document list widget"""
        self.document_list_widget.clear()
        for idx, row in enumerate(self.document_data):
            # Use filename column as document display name
            doc_name = row[self.filename_column] if len(row) > self.filename_column else (row[0] if row else "Unknown")
            
            # Count JPG files (color) and total files (starting after data columns)
            jpg_count = 0
            total_count = 0
            for i in range(self.num_data_columns, len(row)):
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
        
        # Find the first JPG file (starting after data columns)
        for i in range(self.num_data_columns, len(current_row)):
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
        
        # Extract JPG files from current document row (starting after data columns)
        for i in range(self.num_data_columns, len(current_row)):
            image_name = current_row[i].strip()
            if image_name.lower().endswith('.jpg'):
                # Resolve relative paths against the source file's directory
                image_path = image_name if os.path.isabs(image_name) else os.path.join(self.base_dir, image_name)
                self.image_files.append(image_path)
        
        # Update document info label using filename column as display name
        doc_name = current_row[self.filename_column] if len(current_row) > self.filename_column else (current_row[0] if current_row else "Unknown")
        self.doc_info_label.setText(f"Document {self.current_document_index + 1} of {len(self.document_data)}: {doc_name}")
        
        # Update selection in document list
        self.document_list_widget.setCurrentRow(self.current_document_index)
        
        # Populate thumbnails for this document
        self.populate_thumbnails()
        
        # Enable the analyze action and detect button if we have images
        if hasattr(self, 'analyze_action'):
            self.analyze_action.setEnabled(len(self.image_files) > 0)
        if hasattr(self, 'detect_button'):
            self.detect_button.setEnabled(len(self.image_files) > 0)
        # Enable Clone Previous when there is a previous document and images
        if hasattr(self, 'clone_previous_action'):
            has_prev = self.current_document_index > 0
            self.clone_previous_action.setEnabled(has_prev and len(self.image_files) > 0)
    
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
        # Keep Clone Previous state in sync
        if hasattr(self, 'clone_previous_action'):
            has_prev = self.current_document_index > 0 and len(self.image_files) > 0
            self.clone_previous_action.setEnabled(has_prev)

    def clone_previous_pattern(self):
        """Clone the previous document's JPG/TIF pattern to this document.
        For each page position where the previous document is TIF and the current is JPG,
        select the current JPG for conversion (respecting the rule that the first JPG cannot be selected).
        """
        try:
            if not self.document_data or self.current_document_index <= 0:
                QMessageBox.information(self, "No Previous Document", "There is no previous document to clone from.")
                return
            prev_row = self.document_data[self.current_document_index - 1]
            curr_row = self.document_data[self.current_document_index]
            if not prev_row or not curr_row:
                return
            # Compare page counts (non-empty cells from num_data_columns onwards)
            prev_pages = [c.strip() for c in prev_row[self.num_data_columns:] if c and c.strip()]
            curr_pages = [c.strip() for c in curr_row[self.num_data_columns:] if c and c.strip()]
            if len(prev_pages) != len(curr_pages):
                QMessageBox.warning(
                    self,
                    "Page Count Mismatch",
                    f"Previous document has {len(prev_pages)} page(s) while current has {len(curr_pages)}.\n\n"
                    "The pattern will be applied only to the overlapping pages."
                )
            # Identify the first JPG file path in the current document to avoid selecting it
            first_jpg_path = self.get_first_jpg_in_current_document()
            # Iterate over page cells in lockstep
            max_i = min(len(prev_row), len(curr_row))
            applied = 0
            for i in range(self.num_data_columns, max_i):
                prev_cell = prev_row[i].strip() if i < len(prev_row) else ''
                curr_cell = curr_row[i].strip() if i < len(curr_row) else ''
                if not prev_cell or not curr_cell:
                    continue
                # If previous page is TIF and current page is JPG, select the current JPG
                if prev_cell.lower().endswith('.tif') and curr_cell.lower().endswith('.jpg'):
                    # Resolve path just like when populating thumbnails
                    image_path = curr_cell if os.path.isabs(curr_cell) else os.path.join(self.base_dir, curr_cell)
                    # Skip first JPG safeguard
                    if first_jpg_path and image_path == first_jpg_path:
                        continue
                    widget = self._path_to_widget.get(image_path)
                    if widget is not None and not widget.is_checked():
                        widget.checkbox.setChecked(True)
                        applied += 1
            if applied == 0:
                QMessageBox.information(self, "Clone Previous", "No matching pages to select from the previous pattern.")
            else:
                QMessageBox.information(self, "Clone Previous", f"Selected {applied} page(s) to match the previous pattern.")
        except Exception as e:
            QMessageBox.critical(self, "Clone Previous Failed", str(e))
    
    def show_busy_cursor(self, show=True):
        """Show or hide busy cursor"""
        if show:
            QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        else:
            QApplication.restoreOverrideCursor()

    def export_documents(self):
        """Export multipage TIFF and PDF files based on the loaded import file using concurrent processing."""
        if not hasattr(self, 'file_path') or not self.file_path:
            QMessageBox.information(self, "No List", "Please load an import list first")
            return

        # Show wait cursor
        self.show_busy_cursor(True)
        
        # Create and show progress dialog
        self.export_progress_dialog = ExportProgressDialog(self)
        self.export_progress_dialog.show()
        
        # Start export thread
        self.export_thread = ExportThread(self.file_path)
        self.export_thread.progress.connect(self.on_export_progress)
        self.export_thread.finished.connect(self.on_export_finished)
        self.export_thread.start()
    
    def on_export_progress(self, completed, total, doc_name, tiff_success, pdf_success):
        """Handle export progress updates."""
        if self.export_progress_dialog:
            self.export_progress_dialog.update_progress(completed, total, doc_name, tiff_success, pdf_success)
    
    def on_export_finished(self, num_tiffs, num_pdfs):
        """Handle export completion."""
        try:
            # Close progress dialog
            if self.export_progress_dialog:
                self.export_progress_dialog.close()
                self.export_progress_dialog = None
            
            # Hide wait cursor
            self.show_busy_cursor(False)
            
            # Show completion message
            QMessageBox.information(self, "Export Complete", f"Created {num_tiffs} TIFF(s) and {num_pdfs} PDF(s)")
            
        except Exception as e:
            self.show_busy_cursor(False)
            if self.export_progress_dialog:
                self.export_progress_dialog.close()
                self.export_progress_dialog = None
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

        # Update analyze action and detect button state
        if hasattr(self, 'analyze_action'):
            self.analyze_action.setEnabled(len(self.image_files) > 0)
        if hasattr(self, 'detect_button'):
            self.detect_button.setEnabled(len(self.image_files) > 0)
        
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
    
    def _refresh_thumbnail(self, image_path: str):
        """Refresh the thumbnail for a specific image after it has been modified"""
        widget = self._path_to_widget.get(image_path)
        if widget is not None:
            # Get the current cell size for the thumbnail
            cell = widget._cell_size
            target = QSize(max(10, cell - 4), max(10, cell - 24))
            
            # Request a new thumbnail with the updated image
            self.thumbnail_loader.request(image_path, target)

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
            self.current_displayed_image = image_path
            self.is_showing_tiff = False
            self.current_rotation = 0  # Reset rotation when showing new image
            self.current_crop_rect = None  # Reset crop when showing new image
            
            # Clear any existing selection
            self.large_image_label.clear_selection()
            
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
            
            # Enable peek button if we have a JPG image
            if image_path and image_path.lower().endswith('.jpg'):
                self.peek_bw_button.setEnabled(True)
                # Enable rotation and crop buttons for JPG images
                self.rotate_left_button.setEnabled(True)
                self.rotate_right_button.setEnabled(True)
                self.crop_button.setEnabled(True)
                self.save_rotation_button.setEnabled(True)
            else:
                self.peek_bw_button.setEnabled(False)
                # Disable rotation and crop buttons for non-JPG images
                self.rotate_left_button.setEnabled(False)
                self.rotate_right_button.setEnabled(False)
                self.crop_button.setEnabled(False)
                self.save_rotation_button.setEnabled(False)
                
        except Exception as e:
            print(f"Error loading large image {image_path}: {e}")
    
    
    def on_peek_bw_pressed(self):
        """Handle Peek B&W button press - show G4 TIFF preview"""
        if not self.current_displayed_image or self.is_showing_tiff:
            return
        
        # Check if it's a JPG file
        if not self.current_displayed_image.lower().endswith('.jpg'):
            return
        
        # Create or get the G4 TIFF (same path as would be created by conversion)
        tiff_path = os.path.splitext(self.current_displayed_image)[0] + '.tif'
        
        # Create the TIFF if it doesn't exist
        if not os.path.exists(tiff_path):
            tiff_path = convert_image_to_g4_tiff(self.current_displayed_image)
        
        if tiff_path and os.path.exists(tiff_path):
            try:
                pixmap = QPixmap(tiff_path)
                if not pixmap.isNull():
                    # Scale to fit the label while maintaining aspect ratio
                    label_size = self.large_image_label.size()
                    scaled_pixmap = pixmap.scaled(
                        label_size, 
                        Qt.AspectRatioMode.KeepAspectRatio, 
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.large_image_label.setPixmap(scaled_pixmap)
                    self.is_showing_tiff = True
            except Exception as e:
                print(f"Error loading TIFF {tiff_path}: {e}")
    
    def on_peek_bw_released(self):
        """Handle Peek B&W button release - show original JPEG"""
        if not self.current_displayed_image or not self.is_showing_tiff:
            return
        
        # Show the original JPEG again
        try:
            pixmap = QPixmap(self.current_displayed_image)
            if not pixmap.isNull():
                # Scale to fit the label while maintaining aspect ratio
                label_size = self.large_image_label.size()
                scaled_pixmap = pixmap.scaled(
                    label_size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.large_image_label.setPixmap(scaled_pixmap)
                self.is_showing_tiff = False
        except Exception as e:
            print(f"Error loading original image {self.current_displayed_image}: {e}")
    
    def rotate_left(self):
        """Rotate the current image 90 degrees counter-clockwise"""
        if not self.current_displayed_image or self.is_showing_tiff:
            return
        
        self.current_rotation = (self.current_rotation - 90) % 360
        self._apply_rotation()
    
    def rotate_right(self):
        """Rotate the current image 90 degrees clockwise"""
        if not self.current_displayed_image or self.is_showing_tiff:
            return
        
        self.current_rotation = (self.current_rotation + 90) % 360
        self._apply_rotation()
    
    def _apply_rotation(self):
        """Apply the current rotation to the displayed image"""
        if not self.current_displayed_image:
            return
        
        try:
            # Load the original image
            image = Image.open(self.current_displayed_image)
            
            # Apply rotation
            if self.current_rotation != 0:
                rotated_image = image.rotate(-self.current_rotation, expand=True)
            else:
                rotated_image = image
            
            # Convert to QPixmap
            from PIL.ImageQt import ImageQt
            qt_image = ImageQt(rotated_image)
            pixmap = QPixmap.fromImage(qt_image)
            
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
            print(f"Error rotating image {self.current_displayed_image}: {e}")
    
    def crop_image(self):
        """Crop the image to the selected rectangle"""
        if not self.current_displayed_image or self.is_showing_tiff:
            return
        
        # Get the current selection from the image widget
        selection = self.large_image_label.selection_rect
        if not selection:
            QMessageBox.information(self, "No Selection", "Please draw a selection rectangle first")
            return
        
        try:
            # Load the original image
            image = Image.open(self.current_displayed_image)
            
            # Apply rotation first if needed
            if self.current_rotation != 0:
                image = image.rotate(-self.current_rotation, expand=True)
            
            # Convert normalized coordinates to pixel coordinates
            width, height = image.size
            x = int(selection['x'] * width)
            y = int(selection['y'] * height)
            w = int(selection['width'] * width)
            h = int(selection['height'] * height)
            
            # Crop the image
            cropped_image = image.crop((x, y, x + w, y + h))
            
            # Store the crop rectangle for saving
            self.current_crop_rect = selection
            
            # Display the cropped image
            self._display_cropped_image(cropped_image)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to crop image: {str(e)}")
    
    def _display_cropped_image(self, image):
        """Display a cropped image in the preview"""
        try:
            # Convert PIL image to QPixmap
            from PIL.ImageQt import ImageQt
            qt_image = ImageQt(image)
            pixmap = QPixmap.fromImage(qt_image)
            
            if not pixmap.isNull():
                # Scale to fit the label while maintaining aspect ratio
                label_size = self.large_image_label.size()
                scaled_pixmap = pixmap.scaled(
                    label_size, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.large_image_label.setPixmap(scaled_pixmap)
                # Clear selection after cropping
                self.large_image_label.clear_selection()
                
        except Exception as e:
            print(f"Error displaying cropped image: {e}")
    
    def save_rotation(self):
        """Save the current rotation and/or crop to the JPG file"""
        if not self.current_displayed_image or self.is_showing_tiff:
            return
        
        # Check if there are any changes to save
        if self.current_rotation == 0 and not self.current_crop_rect:
            QMessageBox.information(self, "No Changes", "No rotation or crop changes to save")
            return
        
        try:
            # Load the original image
            image = Image.open(self.current_displayed_image)
            
            # Apply rotation first if needed
            if self.current_rotation != 0:
                image = image.rotate(-self.current_rotation, expand=True)
            
            # Apply crop if needed
            if self.current_crop_rect:
                width, height = image.size
                x = int(self.current_crop_rect['x'] * width)
                y = int(self.current_crop_rect['y'] * height)
                w = int(self.current_crop_rect['width'] * width)
                h = int(self.current_crop_rect['height'] * height)
                image = image.crop((x, y, x + w, y + h))
            
            # Save the modified image
            image.save(self.current_displayed_image, "JPEG", quality=95)
            
            # Reset states
            self.current_rotation = 0
            self.current_crop_rect = None
            
            # Reload the image to show the saved version
            self.show_large_image(self.current_displayed_image)
            
            # Refresh the corresponding thumbnail
            self._refresh_thumbnail(self.current_displayed_image)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save changes: {str(e)}")
    
    def analyze_colors(self):
        """Analyze all loaded images to detect monochrome candidates"""
        if not self.image_files:
            QMessageBox.information(self, "No Images", "Please load images first")
            return

        # Disable the analyze action and detect button during analysis
        self.analyze_action.setEnabled(False)
        if hasattr(self, 'detect_button'):
            self.detect_button.setEnabled(False)
        self.show_busy_cursor(True)
        
        # Start color analysis in separate thread
        self.color_analysis_thread = ColorAnalysisThread(self.image_files)
        self.color_analysis_thread.progress.connect(self.show_progress)
        self.color_analysis_thread.analysis_complete.connect(self.on_analysis_complete)
        self.color_analysis_thread.start()
    
    def on_analysis_complete(self, monochrome_candidates: List[str]):
        """Handle completion of color analysis"""
        try:
            # Re-enable the analyze action and detect button
            self.analyze_action.setEnabled(True)
            if hasattr(self, 'detect_button'):
                self.detect_button.setEnabled(True)
            self.show_busy_cursor(False)
            
            # Reset window title
            self.setWindowTitle("Monochrome Detector")
            
            # Auto-check boxes for monochrome candidates concurrently
            checked_count = 0
            with ThreadPoolExecutor() as executor:
                def check_widget(widget):
                    if widget.image_path in monochrome_candidates:
                        widget.checkbox.setChecked(True)
                        self.selected_images.add(widget.image_path)
                        return 1
                    return 0
                checked_counts = list(executor.map(check_widget, self.thumbnail_widgets))
            
        except Exception as e:
            self.analyze_action.setEnabled(True)
            if hasattr(self, 'detect_button'):
                self.detect_button.setEnabled(True)
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
        
        # Update document data (starting after data columns)
        for row in self.document_data:
            for i in range(self.num_data_columns, len(row)):
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


