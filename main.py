import sys
import os
import csv
from pathlib import Path
from typing import List, Dict, Tuple
from PIL import Image, ImageOps
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QGridLayout, QScrollArea, QLabel, 
                            QCheckBox, QMenuBar, QFileDialog, QMessageBox,
                            QFrame, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QAction, QFont


class ImageConverter(QThread):
    """Thread for converting images to G4 TIFF format"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    
    def __init__(self, image_paths: List[str]):
        super().__init__()
        self.image_paths = image_paths
    
    def run(self):
        converted_files = []
        for i, image_path in enumerate(self.image_paths):
            try:
                self.progress.emit(f"Converting {os.path.basename(image_path)}...")
                
                # Check if input file exists
                if not os.path.exists(image_path):
                    self.progress.emit(f"Error: Input file does not exist: {image_path}")
                    continue
                
                # Open image and convert to grayscale
                with Image.open(image_path) as img:
                    # Convert to grayscale
                    gray_img = ImageOps.grayscale(img)
                    
                    # Convert to 1-bit (bilevel) using a fixed threshold so Group 4 is valid
                    # Group 4 requires 1-bit images (BitsPerSample == 1)
                    bw_img = gray_img.point(lambda x: 255 if x >= 128 else 0, mode='1')
                    
                    # Create output path with .tif extension
                    output_path = os.path.splitext(image_path)[0] + '.tif'
                    
                    # Save as G4 TIFF
                    bw_img.save(output_path, 'TIFF', compression='group4')
                    
                    # Verify output file was created
                    if os.path.exists(output_path):
                        converted_files.append((image_path, output_path))
                        self.progress.emit(f"Successfully converted: {os.path.basename(output_path)}")
                    else:
                        self.progress.emit(f"Error: Output file was not created: {output_path}")
                    
            except Exception as e:
                self.progress.emit(f"Error converting {image_path}: {str(e)}")
        
        self.finished.emit(converted_files)


class ThumbnailWidget(QWidget):
    """Widget for displaying a single thumbnail with checkbox"""
    clicked = pyqtSignal(str)
    
    def __init__(self, image_path: str, filename: str):
        super().__init__()
        self.image_path = image_path
        self.filename = filename
        self.setFixedSize(120, 140)
        self.setup_ui()
        self.load_thumbnail()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        
        # Image container with checkbox overlay
        self.image_container = QFrame()
        self.image_container.setFixedSize(116, 116)
        self.image_container.setStyleSheet("border: 1px solid #ccc;")
        self.image_container.mousePressEvent = self.on_image_clicked
        
        # Checkbox overlay
        self.checkbox = QCheckBox()
        self.checkbox.setParent(self.image_container)
        self.checkbox.move(90, 5)
        self.checkbox.stateChanged.connect(self.on_checkbox_changed)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setParent(self.image_container)
        self.image_label.setGeometry(2, 2, 112, 112)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        # Ensure clicks on the image go to the container (so on_image_clicked fires)
        self.image_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Ensure the checkbox stays on top of the image
        self.checkbox.raise_()
        
        layout.addWidget(self.image_container)
        
        # Filename label
        self.filename_label = QLabel(self.filename)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setFont(QFont("Arial", 8))
        self.filename_label.setWordWrap(True)
        layout.addWidget(self.filename_label)
        
        self.setLayout(layout)
    
    def load_thumbnail(self):
        """Load and display thumbnail image"""
        try:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                # Scale to fit thumbnail size
                scaled_pixmap = pixmap.scaled(110, 110, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Error loading thumbnail {self.image_path}: {e}")
    
    def on_image_clicked(self, event):
        """Handle image click"""
        self.checkbox.setChecked(not self.checkbox.isChecked())
        self.clicked.emit(self.image_path)
    
    def on_checkbox_changed(self, state):
        """Handle checkbox state change"""
        self.clicked.emit(self.image_path)
    
    def is_checked(self):
        """Check if this thumbnail is selected"""
        return self.checkbox.isChecked()


class MonochromeDetector(QMainWindow):
    def __init__(self):
        super().__init__()
        self.document_data = []
        self.image_files = []
        self.thumbnail_widgets = []
        self.selected_images = set()
        self.converter_thread = None
        
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
        
        # Convert action
        convert_action = QAction('Convert', self)
        convert_action.triggered.connect(self.convert_selected)
        file_menu.addAction(convert_action)
    
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
        thumbnail_container.setMaximumWidth(600)
        
        layout = QVBoxLayout()
        thumbnail_container.setLayout(layout)
        
        # Scroll area for thumbnails
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Grid widget for thumbnails
        self.thumbnail_grid = QWidget()
        self.grid_layout = QGridLayout()
        self.grid_layout.setSpacing(5)
        self.thumbnail_grid.setLayout(self.grid_layout)
        
        self.scroll_area.setWidget(self.thumbnail_grid)
        layout.addWidget(self.scroll_area)
        
        parent_layout.addWidget(thumbnail_container)
    
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
        
        parent_layout.addWidget(image_container)
    
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
                
                QMessageBox.information(self, "Success", f"Loaded {len(self.image_files)} JPG files from {len(self.document_data)} documents")
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")
    
    def populate_thumbnails(self):
        """Populate thumbnail grid with images"""
        # Clear existing thumbnails
        for widget in self.thumbnail_widgets:
            widget.deleteLater()
        self.thumbnail_widgets.clear()
        # Clear selected images set
        self.selected_images.clear()
        
        # Create thumbnails in 4 column grid
        cols = 4
        for i, image_path in enumerate(self.image_files):
            row = i // cols
            col = i % cols
            
            filename = os.path.basename(image_path)
            thumbnail = ThumbnailWidget(image_path, filename)
            thumbnail.clicked.connect(self.on_thumbnail_clicked)
            
            self.grid_layout.addWidget(thumbnail, row, col)
            self.thumbnail_widgets.append(thumbnail)
    
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
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

