from PyQt6.QtWidgets import QWidget, QVBoxLayout, QFrame, QCheckBox, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QPixmap, QFont


class ThumbnailWidget(QWidget):
    """Widget for displaying a single thumbnail with checkbox"""
    clicked = pyqtSignal(str)
    
    def __init__(self, image_path: str, filename: str):
        super().__init__()
        self.image_path = image_path
        self.filename = filename
        # Default; will be overridden dynamically
        self._cell_size = 140
        self.setFixedSize(self._cell_size, self._cell_size)
        self.setup_ui()
        self.load_thumbnail()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Image container with checkbox overlay
        self.image_container = QFrame()
        self.image_container.setFixedSize(self._cell_size, self._cell_size)
        self.image_container.setStyleSheet("border: 1px solid #ccc;")
        self.image_container.mousePressEvent = self.on_image_clicked
        
        # Checkbox overlay
        self.checkbox = QCheckBox()
        self.checkbox.setParent(self.image_container)
        self.checkbox.move(max(0, self._cell_size - 30), 5)
        self.checkbox.stateChanged.connect(self.on_checkbox_changed)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setParent(self.image_container)
        self.image_label.setGeometry(2, 2, self._cell_size - 4, self._cell_size - 24)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        # Ensure clicks on the image go to the container (so on_image_clicked fires)
        self.image_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Ensure the checkbox stays on top of the image
        self.checkbox.raise_()
        
        # Filename overlay inside the cell (keeps the total cell square)
        self.filename_label = QLabel(self.filename, self.image_container)
        self.filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.filename_label.setFont(QFont("Arial", 8))
        self.filename_label.setStyleSheet(
            "background-color: rgba(0,0,0,0.45); color: white; padding: 2px;"
        )
        self.filename_label.setWordWrap(True)
        self.filename_label.raise_()

        layout.addWidget(self.image_container)
        
        self.setLayout(layout)
    
    def load_thumbnail(self):
        """Load and display thumbnail image"""
        try:
            pixmap = QPixmap(self.image_path)
            if not pixmap.isNull():
                # Scale to fit current image label size
                target_size = QSize(self.image_label.width(), self.image_label.height())
                scaled_pixmap = pixmap.scaled(
                    target_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Error loading thumbnail {self.image_path}: {e}")

    def set_cell_size(self, cell_size: int):
        """Set the outer square cell size and update layout accordingly."""
        if cell_size == self._cell_size:
            return
        self._cell_size = max(60, cell_size)
        # Update outer widget and container
        self.setFixedSize(self._cell_size, self._cell_size)
        self.image_container.setFixedSize(self._cell_size, self._cell_size)
        # Update child geometries
        self.checkbox.move(max(0, self._cell_size - 30), 5)
        # Reserve ~20px for filename bar
        image_area_height = max(10, self._cell_size - 24)
        self.image_label.setGeometry(2, 2, self._cell_size - 4, image_area_height)
        self.filename_label.setGeometry(2, self._cell_size - 20, self._cell_size - 4, 18)
        # Rescale pixmap
        self.load_thumbnail()
    
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