from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSlider


class PlaybackPanel(QWidget):
    """
    A widget containing UI controls for audio playback.
    """
    # Signals
    play_requested = Signal()
    pause_requested = Signal()
    stop_requested = Signal()
    seek_requested = Signal(int)  # Emits frame position

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # UI Elements
        self.play_button = QPushButton("Play")
        self.pause_button = QPushButton("Pause")
        self.stop_button = QPushButton("Stop")
        self.filename_label = QLabel("No file loaded")
        self.playback_slider = QSlider()
        self.time_label = QLabel("0:00 / 0:00")
        
        # Setup UI
        self._setup_ui()
        
        # Connect signals
        self.play_button.clicked.connect(self.play_requested.emit)
        self.pause_button.clicked.connect(self.pause_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self.playback_slider.sliderMoved.connect(self.seek_requested.emit)
    
    def _setup_ui(self):
        """
        Set up the layout and appearance of the playback panel.
        """
        # Main layout
        main_layout = QHBoxLayout(self)
        
        # Left layout for buttons
        button_layout = QVBoxLayout()
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.pause_button)
        button_layout.addWidget(self.stop_button)
        
        # Right layout for filename and slider
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.filename_label)
        
        # Bottom layout for slider and time label
        slider_layout = QHBoxLayout()
        slider_layout.addWidget(self.playback_slider)
        slider_layout.addWidget(self.time_label)
        
        right_layout.addLayout(slider_layout)
        
        # Add layouts to main layout
        main_layout.addLayout(button_layout)
        main_layout.addLayout(right_layout)
        
        # Set initial states
        self.playback_slider.setOrientation(Qt.Orientation.Horizontal)  # Horizontal
        self.playback_slider.setRange(0, 0)  # Disabled until a file is loaded
        self.pause_button.setEnabled(False)  # Disabled initially
    
    @Slot(str, float, float)
    def update_ui(self, state: str, filename: str = "", duration: float = 0.0, position: float = 0.0):
        """
        Update the UI elements based on the current playback state.
        
        Args:
            state: Current playback state ('playing', 'paused', 'stopped')
            filename: Name of the currently loaded file
            duration: Total duration of the audio in seconds
            position: Current playback position in seconds
        """
        self.filename_label.setText(filename if filename else "No file loaded")
        
        if state == 'playing':
            self.play_button.setEnabled(False)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            self.playback_slider.setEnabled(True)
        elif state == 'paused':
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.playback_slider.setEnabled(True)
        else:  # stopped
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(False)
            self.stop_button.setEnabled(False)
            self.playback_slider.setEnabled(False)
            self.playback_slider.setValue(0) # Reset slider to beginning
        
        # Update slider range if duration is provided
        if duration > 0:
            self.playback_slider.setRange(0, int(duration))
        elif state == 'stopped': # If no duration and stopped, ensure range is 0
            self.playback_slider.setRange(0,0)
        
        # Update time display
        self._update_time_display(position if position > 0 else 0.0, duration)
    
    @Slot(float)
    def update_playback_position(self, position: float):
        """
        Update the playback position slider and time display.
        
        Args:
            position: Current playback position in seconds
        """
        if not self.playback_slider.isSliderDown():  # Only update if user is not dragging
            self.playback_slider.setValue(int(position))
        self._update_time_display(position, self.playback_slider.maximum())
    
    def _update_time_display(self, position: float, duration: float):
        """
        Update the time label with current position and total duration.
        
        Args:
            position: Current playback position in seconds
            duration: Total duration of the audio in seconds
        """
        current_time = self._format_time(position)
        total_time = self._format_time(duration)
        self.time_label.setText(f"{current_time} / {total_time}")
    
    def _format_time(self, seconds: float) -> str:
        """
        Format time in seconds to a MM:SS string.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string (MM:SS)
        """
        if seconds < 0:
            return "0:00"
        
        minutes = int(seconds // 60)
        seconds = int(seconds % 60)
        return f"{minutes}:{seconds:02d}"