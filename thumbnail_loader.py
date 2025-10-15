from PyQt6.QtCore import QObject, pyqtSignal, QRunnable, QThreadPool
from PyQt6.QtGui import QImageReader, QImage
from PyQt6.QtCore import QSize


class ThumbnailSignals(QObject):
    done = pyqtSignal(str, QImage)   # (path, image)
    error = pyqtSignal(str, str)     # (path, message)


class ThumbnailJob(QRunnable):
    def __init__(self, path: str, target_size: QSize, signals: ThumbnailSignals):
        super().__init__()
        self.path = path
        self.target_size = target_size
        self.signals = signals

    def run(self):
        reader = QImageReader(self.path)
        reader.setAutoTransform(True)
        if self.target_size and self.target_size.isValid():
            reader.setScaledSize(self.target_size)
        image = reader.read()
        if image.isNull():
            self.signals.error.emit(self.path, reader.errorString() or "Failed to load")
        else:
            self.signals.done.emit(self.path, image)


class ThumbnailLoader(QObject):
    thumbnailReady = pyqtSignal(str, QImage)
    thumbnailFailed = pyqtSignal(str, str)

    def __init__(self, max_threads: int = 4):
        super().__init__()
        self.pool = QThreadPool.globalInstance()
        if max_threads and isinstance(max_threads, int):
            try:
                self.pool.setMaxThreadCount(max_threads)
            except Exception:
                pass

    def request(self, path: str, target_size: QSize):
        signals = ThumbnailSignals()
        signals.done.connect(self.thumbnailReady)
        signals.error.connect(self.thumbnailFailed)
        job = ThumbnailJob(path, target_size, signals)
        self.pool.start(job)
