import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import pyaudio
from pydub import AudioSegment
import threading
from threading import Event
import time
import random

class DAWApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Advanced DAW")
        self.root.geometry("1200x600")
        self.audio_clips = []
        self.current_audio = None
        self.pyaudio_instance = pyaudio.PyAudio()
        self.audio_stream = None
        self.is_playing = False
        self.pause_event = Event()
        self.playback_thread = None
        self.playback_stopped_manually = False  # Flag to indicate manual stop

        # Initialize BPM and Beats Per Bar
        self.bpm = 120
        self.beats_per_bar = 4  # Time signature is 4/4
        self.subdivision = 1    # Default subdivision for grid and snapping

        # Map pixels to time
        self.pixels_per_second = 100  # Fixed value; adjust for zoom level
        self.update_time_mapping()    # Initialize pixels_per_beat and pixels_per_bar

        # Playhead position in pixels
        self.playhead_position = 0
        self.playback_start_position = 0

        # Bind the close event to the on_close method
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Create the main layout
        self.create_controls()
        self.create_timeline()

    def on_close(self):
        """Handle cleanup on application exit."""
        self.stop_audio()
        self.pyaudio_instance.terminate()  # Release PyAudio resources
        self.root.destroy()

    def create_controls(self):
        """Create playback controls, BPM slider, and division selector."""
        control_frame = tk.Frame(self.root, bg="lightgrey", height=60)
        control_frame.pack(fill=tk.X)

        # Play Button
        self.play_button = tk.Button(control_frame, text="Play", command=self.play_audio, width=10)
        self.play_button.pack(side=tk.LEFT, padx=10)

        # Pause Button
        self.pause_button = tk.Button(control_frame, text="Pause", command=self.pause_audio, width=10)
        self.pause_button.pack(side=tk.LEFT, padx=10)

        # BPM Label and Slider
        bpm_label = tk.Label(control_frame, text="BPM:", bg="lightgrey", font=("Arial", 12))
        bpm_label.pack(side=tk.LEFT, padx=10)

        bpm_slider = tk.Scale(
            control_frame, from_=60, to=240, orient=tk.HORIZONTAL, bg="lightgrey", command=self.update_bpm
        )
        bpm_slider.set(self.bpm)
        bpm_slider.pack(side=tk.LEFT, padx=10)

        # Current BPM Display
        self.bpm_display = tk.Label(control_frame, text=f"{self.bpm} BPM", bg="lightgrey", font=("Arial", 12))
        self.bpm_display.pack(side=tk.LEFT, padx=10)

        # Volume Slider
        volume_label = tk.Label(control_frame, text="Volume:", bg="lightgrey", font=("Arial", 12))
        volume_label.pack(side=tk.LEFT, padx=10)

        self.volume_slider = tk.Scale(
            control_frame, from_=-50, to=5, orient=tk.HORIZONTAL, bg="lightgrey", command=self.update_volume
        )
        self.volume_slider.set(-20)  # Default volume level
        self.volume_slider.pack(side=tk.LEFT, padx=10)

        # Division Selector
        division_label = tk.Label(control_frame, text="Grid Division:", bg="lightgrey", font=("Arial", 12))
        division_label.pack(side=tk.LEFT, padx=10)

        self.division_var = tk.StringVar()
        self.division_var.set("1/1")  # Default division
        divisions = ["1/1", "1/2", "1/3", "1/4"]
        self.division_map = {"1/1": 1, "1/2": 2, "1/3": 3, "1/4": 4}
        division_menu = tk.OptionMenu(control_frame, self.division_var, *divisions, command=self.update_division)
        division_menu.config(width=5)
        division_menu.pack(side=tk.LEFT, padx=10)

        # Add Import Button
        import_button = tk.Button(control_frame, text="Import Audio", command=self.import_audio)
        import_button.pack(side=tk.LEFT, padx=10)

        # Add Export Button
        export_button = tk.Button(control_frame, text="Export Arrangement", command=self.export_audio)
        export_button.pack(side=tk.LEFT, padx=10)

    def create_timeline(self):
        """Create timeline and tracks."""
        timeline_frame = tk.Frame(self.root, bg="white")
        timeline_frame.pack(fill=tk.BOTH, expand=True)

        # Create a frame to hold the track labels and canvas
        main_frame = tk.Frame(timeline_frame)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Track Labels Frame
        tracks_frame = tk.Frame(main_frame, width=100, bg="lightgrey")
        tracks_frame.pack(side=tk.LEFT, fill=tk.Y)

        # Add track labels
        for track_num in range(1, 6):
            track_label = tk.Label(tracks_frame, text=f"Track {track_num}", bg="lightgrey", width=12, anchor="w")
            track_label.place(x=0, y=(track_num - 1) * 100, height=100)

        # Create a frame to hold the ruler and timeline canvas
        canvas_frame = tk.Frame(main_frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, side=tk.RIGHT)

        # Ruler Canvas
        self.ruler_canvas = tk.Canvas(canvas_frame, bg="lightgrey", height=30)  # Increased height
        self.ruler_canvas.pack(fill=tk.X, side=tk.TOP)

        # Timeline Canvas
        self.timeline_canvas = tk.Canvas(canvas_frame, bg="white")
        self.timeline_canvas.pack(fill=tk.BOTH, expand=True, side=tk.LEFT)

        # Vertical Scrollbar
        v_scrollbar = tk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self.timeline_canvas.yview)
        v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.timeline_canvas.config(yscrollcommand=v_scrollbar.set)

        # Horizontal Scrollbar
        h_scrollbar = tk.Scrollbar(timeline_frame, orient=tk.HORIZONTAL, command=self.xview)
        h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.timeline_canvas.config(xscrollcommand=h_scrollbar.set)
        self.ruler_canvas.config(xscrollcommand=h_scrollbar.set)

        # Set initial scroll region (supports 10 minutes)
        total_seconds = 600  # 10 minutes
        total_width = total_seconds * self.pixels_per_second
        self.timeline_canvas.config(scrollregion=(0, 0, total_width, 500))
        self.ruler_canvas.config(scrollregion=(0, 0, total_width, 30))

        # Create Playhead
        self.playhead = self.timeline_canvas.create_line(0, 0, 0, 500, fill="red", width=2)
        self.ruler_playhead = self.ruler_canvas.create_line(0, 0, 0, 30, fill="red", width=2)

        # Draw Grid
        self.draw_ruler()
        self.draw_grid()

        # Bindings for the playhead movement
        self.ruler_canvas.bind("<Button-1>", self.move_playhead_click)
        self.ruler_canvas.bind("<B1-Motion>", self.move_playhead_drag)

        # Enable drag-and-drop
        self.timeline_canvas.bind("<Button-1>", self.select_clip)
        self.timeline_canvas.bind("<B1-Motion>", self.move_clip)
        self.timeline_canvas.bind("<ButtonRelease-1>", self.snap_clip)

        # Bind delete key
        self.root.bind("<BackSpace>", self.delete_selected_clip)

    def xview(self, *args):
        """Scroll both the timeline and ruler canvases."""
        self.timeline_canvas.xview(*args)
        self.ruler_canvas.xview(*args)

    def update_time_mapping(self):
        """Update pixels_per_second, pixels_per_beat, and pixels_per_bar based on BPM."""
        self.pixels_per_second = 100  # Fixed value for consistent time mapping
        self.pixels_per_beat = self.pixels_per_second * 60 / self.bpm
        self.pixels_per_bar = self.pixels_per_beat * self.beats_per_bar

    def draw_ruler(self):
        """Draw time ruler with bars and beats."""
        self.ruler_canvas.delete("all")  # Clear existing ruler

        # Get the current scrollregion to know how wide to draw the ruler
        scrollregion = self.ruler_canvas.cget("scrollregion")  # e.g., "0 0 60000 30"
        x0, y0, x1, y1 = map(int, scrollregion.split())

        # Draw ruler markings
        x = 0
        bar_number = 1
        while x <= x1:
            # Bar line
            self.ruler_canvas.create_line(x, 0, x, 30, fill="black")
            # Label the bar number
            self.ruler_canvas.create_text(x + 2, 2, anchor='nw', text=f"Bar {bar_number}", fill="black", font=("Arial", 8))
            bar_number += 1

            # Draw beat ticks within the bar
            beat_x = x + self.pixels_per_beat
            for beat in range(1, self.beats_per_bar):
                self.ruler_canvas.create_line(beat_x, 15, beat_x, 30, fill="black")
                beat_x += self.pixels_per_beat

            x += self.pixels_per_bar

    def draw_grid(self):
        """Draw snap-on grid with beats and bars."""
        self.timeline_canvas.delete("grid")  # Clear existing grid

        # Get the current scrollregion to know how wide to draw the grid
        scrollregion = self.timeline_canvas.cget("scrollregion")  # e.g., "0 0 60000 500"
        x0, y0, x1, y1 = map(int, scrollregion.split())

        # Draw vertical grid lines for bars and beats
        x = 0
        while x <= x1:
            # Bar line
            self.timeline_canvas.create_line(x, 0, x, y1, fill="black", width=1, tags="grid")
            beat_x = x
            for beat in range(1, self.beats_per_bar + 1):
                beat_x += self.pixels_per_beat
                # Beat lines
                if beat <= self.beats_per_bar:
                    self.timeline_canvas.create_line(beat_x, 0, beat_x, y1, fill="grey", dash=(2, 2), tags="grid")
                # Draw subdivisions within the beat
                if self.subdivision > 1:
                    subdivision_step = self.pixels_per_beat / self.subdivision
                    subdivision_x = beat_x - self.pixels_per_beat
                    for sub in range(1, self.subdivision):
                        subdivision_x += subdivision_step
                        self.timeline_canvas.create_line(subdivision_x, 0, subdivision_x, y1, fill="lightgrey", dash=(1, 1), tags="grid")
            x += self.pixels_per_bar

        # Draw horizontal track dividers
        for j in range(0, 500, 100):  # Horizontal track dividers
            self.timeline_canvas.create_line(0, j, x1, j, fill="black", width=1, tags="grid")

        # Add bottom boundary for Track 5
        self.timeline_canvas.create_line(0, 500, x1, 500, fill="black", width=1, tags="grid")

        # Bring clips to front
        for clip in self.audio_clips:
            self.timeline_canvas.tag_raise(clip["background_id"])
            self.timeline_canvas.tag_raise(clip["outline_id"])
            self.timeline_canvas.tag_raise(clip["text_id"])
            for line_id in clip["waveform_ids"]:
                self.timeline_canvas.tag_raise(line_id)
        # Bring playhead to front
        self.timeline_canvas.tag_raise(self.playhead)

    def move_playhead_click(self, event):
        """Move playhead to the clicked position on the ruler."""
        x = self.ruler_canvas.canvasx(event.x)
        self.set_playhead_position(x)

    def move_playhead_drag(self, event):
        """Move playhead while dragging on the ruler."""
        x = self.ruler_canvas.canvasx(event.x)
        self.set_playhead_position(x)

    def set_playhead_position(self, x):
        """Set the playhead position."""
        x = max(0, x)
        self.playhead_position = x
        self.timeline_canvas.coords(self.playhead, x, 0, x, 500)
        self.ruler_canvas.coords(self.ruler_playhead, x, 0, x, 30)

    def import_audio(self):
        """Allow the user to import an audio file."""
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio Files", "*.wav *.mp3"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            # Load the audio file using PyDub
            audio = AudioSegment.from_file(file_path)

            # Convert to raw audio data for PyAudio playback
            raw_data = audio.raw_data
            frame_rate = audio.frame_rate
            channels = audio.channels
            sample_width = audio.sample_width

            track_num = len(self.audio_clips) % 5 + 1
            x_position = 100 + len(self.audio_clips) * 100
            self.add_audio_clip(file_path, raw_data, frame_rate, channels, sample_width, track_num, x_position)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to import audio: {e}")

    def get_random_color(self):
        colors = [
            "#b8cdff",
            "#ffb8f1",
            "#ffeab8",
            "#b8ffc6",
            "#ff8787",
            "#c3ff87",
            "#87ffff",
            "#c387ff"
        ]
        return random.choice(colors)

    def add_audio_clip(self, file_path, raw_data, frame_rate, channels, sample_width, track_num, x_position):
        """Add an audio clip to the timeline."""
        # Determine track Y positions
        waveform_y = (track_num - 1) * 100 + 50  # Centered within the track

        # Standardize sample rate and channels
        base_sample_rate = 44100  # Standard sample rate
        base_channels = 2  # Stereo
        base_sample_width = 2  # 16 bits

        audio_segment = AudioSegment(
            data=raw_data,
            sample_width=sample_width,
            frame_rate=frame_rate,
            channels=channels
        )

        # Set to base sample rate and channels
        audio_segment = audio_segment.set_frame_rate(base_sample_rate)
        audio_segment = audio_segment.set_channels(base_channels)
        audio_segment = audio_segment.set_sample_width(base_sample_width)

        # Update raw_data, frame_rate, channels, sample_width
        raw_data = audio_segment.raw_data
        frame_rate = audio_segment.frame_rate
        channels = audio_segment.channels
        sample_width = audio_segment.sample_width

        # Calculate duration
        duration_ms = len(audio_segment)
        duration_in_seconds = duration_ms / 1000

        # Calculate clip width based on duration
        clip_width = duration_in_seconds * self.pixels_per_second

        color = self.get_random_color()
        # Draw opaque background

        background_id = self.timeline_canvas.create_rectangle(
            x_position, waveform_y - 15, x_position + clip_width, waveform_y + 15,
            fill=color, outline="", tags="audio_clip_bg"
        )

        # Store start time in seconds
        start_time_seconds = x_position / self.pixels_per_second

        # Draw outline (beginning and end of file)
        outline_id = self.timeline_canvas.create_rectangle(
            x_position, waveform_y - 15, x_position + clip_width, waveform_y + 15, outline="blue", width=2
        )

        # Draw filename and duration
        filename = file_path.split("/")[-1]
        max_text_width = clip_width - 10  # Adjust based on clip width
        if len(filename) * 7 > max_text_width and max_text_width > 0:
            filename = filename[:int(max_text_width / 7) - 3] + "..."

        text_id = self.timeline_canvas.create_text(
            x_position + 5, waveform_y - 25,
            text=f"{filename} ({duration_in_seconds:.2f}s)",
            anchor="w", fill="black"
        )

        # Draw waveform
        waveform_ids = self.create_waveform(raw_data, sample_width, waveform_y, x_position, clip_width)

        # Store clip information
        self.audio_clips.append({
            "background_id": background_id,
            "outline_id": outline_id,
            "text_id": text_id,
            "waveform_ids": waveform_ids,
            "raw_data": raw_data,
            "frame_rate": frame_rate,
            "channels": channels,
            "sample_width": sample_width,
            "x": x_position,
            "start_time_seconds": start_time_seconds,
            "track": track_num,
            "duration_seconds": duration_in_seconds,
            "clip_width": clip_width
        })

        # Bring clip to front
        self.timeline_canvas.tag_raise(background_id)
        self.timeline_canvas.tag_raise(outline_id)
        self.timeline_canvas.tag_raise(text_id)
        for line_id in waveform_ids:
            self.timeline_canvas.tag_raise(line_id)
        # Bring playhead to front
        self.timeline_canvas.tag_raise(self.playhead)

        # Update scroll region
        self.update_scroll_region()

    def create_waveform(self, raw_data, sample_width, y_offset, x_offset, clip_width):
        """Create an optimized waveform visualization."""
        # Convert raw audio data to a numpy array
        audio_array = np.frombuffer(raw_data, dtype=np.int16)
        max_height = 20
        max_points = 1000  # Limit the number of points to prevent GUI lag

        # Calculate the number of points for the waveform
        num_points = min(int(clip_width), max_points)
        if num_points <= 1:
            num_points = 2  # Ensure at least two points for drawing

        # Downsample the audio array to fit the max_points
        indices = np.linspace(0, len(audio_array) - 1, num=num_points, dtype=int)
        sampled_audio = audio_array[indices]

        # Normalize the audio data
        max_value = np.max(np.abs(audio_array))
        if max_value == 0:
            max_value = 1  # Prevent division by zero

        # Calculate the x and y coordinates for the waveform
        x_values = np.linspace(x_offset, x_offset + clip_width, num=num_points)
        y_values = y_offset - (sampled_audio / max_value) * max_height

        # Prepare the points for drawing
        points = []
        for x, y in zip(x_values, y_values):
            points.extend([x, y])

        # Draw the waveform as a single line
        line_id = self.timeline_canvas.create_line(points, fill="black", smooth=True)
        waveform_ids = [line_id]

        return waveform_ids

    def select_clip(self, event):
        """Select an audio clip for dragging."""
        self.selected_clip = None
        for clip in self.audio_clips:
            # Reset previous clip outline to default
            self.timeline_canvas.itemconfig(clip["outline_id"], outline="blue", width=2)

            x_coords = self.timeline_canvas.coords(clip["outline_id"])
            if x_coords[0] <= self.timeline_canvas.canvasx(event.x) <= x_coords[2] and \
               x_coords[1] <= self.timeline_canvas.canvasy(event.y) <= x_coords[3]:
                self.selected_clip = clip
                self.drag_start_x = self.timeline_canvas.canvasx(event.x)
                self.drag_start_y = self.timeline_canvas.canvasy(event.y)

                # Highlight selected clip
                self.timeline_canvas.itemconfig(clip["outline_id"], outline="red", width=3)
                break

    def move_clip(self, event):
        """Move an audio clip within the timeline."""
        if not self.selected_clip:
            return

        new_x = self.timeline_canvas.canvasx(event.x)
        new_y = self.timeline_canvas.canvasy(event.y)
        dx = new_x - self.drag_start_x
        dy = new_y - self.drag_start_y

        # Get the current position of the clip
        x_coords = self.timeline_canvas.coords(self.selected_clip["outline_id"])

        # Prevent moving out of left bound
        if x_coords[0] + dx < 0:
            dx = -x_coords[0]
        # Allow moving to the right without restriction

        # Prevent moving out of vertical bounds
        if x_coords[1] + dy < 0:
            dy = -x_coords[1]
        if x_coords[3] + dy > self.timeline_canvas.canvasy(self.timeline_canvas.winfo_height()):
            dy = self.timeline_canvas.canvasy(self.timeline_canvas.winfo_height()) - x_coords[3]

        # Move all components of the clip
        self.timeline_canvas.move(self.selected_clip["background_id"], dx, dy)
        self.timeline_canvas.move(self.selected_clip["outline_id"], dx, dy)
        self.timeline_canvas.move(self.selected_clip["text_id"], dx, dy)
        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.move(line_id, dx, dy)

        # Update drag start positions
        self.drag_start_x = new_x
        self.drag_start_y = new_y

        # Bring clip to front
        self.timeline_canvas.tag_raise(self.selected_clip["background_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["outline_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["text_id"])
        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.tag_raise(line_id)
        # Bring playhead to front
        self.timeline_canvas.tag_raise(self.playhead)

        # Update scroll region
        self.update_scroll_region()

    def snap_clip(self, event):
        """Snap the audio clip to the nearest grid point."""
        if not self.selected_clip:
            return

        # Get the current position of the clip
        x_coords = self.timeline_canvas.coords(self.selected_clip["outline_id"])
        x = x_coords[0]
        y = x_coords[1]

        # Snap horizontally to nearest subdivision
        subdivision_pixels = self.pixels_per_beat / self.subdivision
        new_x = round(x / subdivision_pixels) * subdivision_pixels
        dx = new_x - x

        # Snap vertically to nearest track
        new_track = max(1, min(5, round(y / 100) + 1))
        new_y = (new_track - 1) * 100 + 50 - 15
        dy = new_y - y

        # Move all components
        self.timeline_canvas.move(self.selected_clip["background_id"], dx, dy)
        self.timeline_canvas.move(self.selected_clip["outline_id"], dx, dy)

        # Adjust text position
        rect_coords = self.timeline_canvas.coords(self.selected_clip["outline_id"])
        text_x = rect_coords[0] + 5
        text_y = rect_coords[1] - 10
        self.timeline_canvas.coords(self.selected_clip["text_id"], text_x, text_y)

        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.move(line_id, dx, dy)

        # Update track information
        self.selected_clip["track"] = new_track

        # Update 'x' and 'start_time_seconds' in clip data
        self.selected_clip["x"] = rect_coords[0]
        self.selected_clip["start_time_seconds"] = rect_coords[0] / self.pixels_per_second

        # Bring clip to front
        self.timeline_canvas.tag_raise(self.selected_clip["background_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["outline_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["text_id"])
        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.tag_raise(line_id)
        # Bring playhead to front
        self.timeline_canvas.tag_raise(self.playhead)

        # Update scroll region
        self.update_scroll_region()

    def update_clips_positions(self):
        """Update the positions and widths of clips when time mapping changes."""
        for clip in self.audio_clips:
            # Recalculate x_position
            x_position = clip["start_time_seconds"] * self.pixels_per_second
            # Recalculate clip width
            clip_width = clip["duration_seconds"] * self.pixels_per_second
            # Update the clip's graphical elements
            y1, y2 = self.timeline_canvas.coords(clip["outline_id"])[1], self.timeline_canvas.coords(clip["outline_id"])[3]
            self.timeline_canvas.coords(clip["background_id"], x_position, y1, x_position + clip_width, y2)
            self.timeline_canvas.coords(clip["outline_id"], x_position, y1, x_position + clip_width, y2)
            # Update text position
            text_x = x_position + 5
            text_y = y1 - 10
            self.timeline_canvas.coords(clip["text_id"], text_x, text_y)
            # Update waveform
            waveform_y = (clip["track"] - 1) * 100 + 50  # Centered within the track
            # Delete old waveform
            for line_id in clip["waveform_ids"]:
                self.timeline_canvas.delete(line_id)
            # Create new waveform
            waveform_ids = self.create_waveform(
                clip["raw_data"],
                clip["sample_width"],
                waveform_y,
                x_position,
                clip_width
            )
            clip["waveform_ids"] = waveform_ids
            # Update x and clip_width in clip data
            clip["x"] = x_position
            clip["clip_width"] = clip_width

        # Bring clips to front after updating positions
        for clip in self.audio_clips:
            self.timeline_canvas.tag_raise(clip["background_id"])
            self.timeline_canvas.tag_raise(clip["outline_id"])
            self.timeline_canvas.tag_raise(clip["text_id"])
            for line_id in clip["waveform_ids"]:
                self.timeline_canvas.tag_raise(line_id)
        # Bring playhead to front
        self.timeline_canvas.tag_raise(self.playhead)

    def update_scroll_region(self):
        """Update the scroll region based on BPM and clips' positions."""
        # Ensure the scroll region is at least as wide as the furthest clip
        max_clip_x = 0
        for clip in self.audio_clips:
            x_coords = self.timeline_canvas.coords(clip["outline_id"])
            if x_coords[2] > max_clip_x:
                max_clip_x = x_coords[2]
        total_width = max_clip_x + 100  # Add padding

        # Ensure the scroll region covers at least 10 minutes
        min_total_width = 600 * self.pixels_per_second  # 10 minutes
        total_width = max(total_width, min_total_width)

        # Update scroll regions
        self.timeline_canvas.config(scrollregion=(0, 0, total_width, 500))
        self.ruler_canvas.config(scrollregion=(0, 0, total_width, 30))
        # Redraw grid and ruler
        self.draw_ruler()
        self.draw_grid()

    def play_audio(self):
        """Play or Restart the playback."""
        if self.play_button['text'] == 'Play':
            # Start playback from current playhead position
            if self.is_playing:
                # Should not happen, but just in case
                self.stop_audio()
            self.is_playing = True
            self.playback_stopped_manually = False  # Reset the flag
            self.pause_event.clear()
            self.pause_button.config(text="Pause")  # Ensure pause button is in correct state
            self.play_button.config(text="Restart")  # Change button text to "Restart"
            self.playback_start_position = self.playhead_position
            self.playback_thread = threading.Thread(target=self._play_clips)
            self.playback_thread.start()
        elif self.play_button['text'] == 'Restart':
            # Stop playback and reset playhead to beginning
            if self.is_playing:
                self.stop_audio()
                # Wait until the playback thread has fully stopped
                if self.playback_thread and self.playback_thread.is_alive():
                    self.playback_thread.join()
                    self.playback_thread = None
            self.reset_playhead()
            self.play_button.config(text="Play")  # Change button text back to "Play"

    def stop_audio(self):
        """Stop audio playback."""
        self.is_playing = False
        self.pause_event.clear()
        self.playback_stopped_manually = True  # Indicate that playback was stopped manually
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1)
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None
        # Reset pause button text
        self.pause_button.config(text="Pause")
        self.playback_thread = None
        # Reset play button text
        self.play_button.config(text="Play")

    def _play_clips(self):
        """Handle the actual playback of all clips."""
        # Prepare the combined audio
        combined_audio = self.mix_audio_clips()

        if combined_audio is None:
            self.is_playing = False
            return

        # Calculate start time in ms from playhead position
        start_time_ms = (self.playback_start_position / self.pixels_per_second) * 1000

        if start_time_ms >= len(combined_audio):
            # Playhead is beyond the length of audio
            messagebox.showinfo("Playback", "Playhead is beyond the length of the arrangement.")
            self.is_playing = False
            return

        # Trim the audio to start from the playhead position
        combined_audio = combined_audio[start_time_ms:]

        try:
            self.audio_stream = self.pyaudio_instance.open(
                format=self.pyaudio_instance.get_format_from_width(combined_audio.sample_width),
                channels=combined_audio.channels,
                rate=int(combined_audio.frame_rate),
                output=True,
                frames_per_buffer=1024
            )
            data = combined_audio.raw_data
            sample_rate = combined_audio.frame_rate
            channels = combined_audio.channels
            sample_width = combined_audio.sample_width

            chunk_frames = 1024  # Number of frames per chunk
            chunk_size = chunk_frames * sample_width * channels  # Size of each chunk in bytes
            total_frames_played = 0
            total_frames = len(data) // (sample_width * channels)

            while total_frames_played < total_frames and self.is_playing:
                if self.pause_event.is_set():
                    # When paused, simply wait
                    while self.pause_event.is_set() and self.is_playing:
                        time.sleep(0.1)
                start_byte = total_frames_played * sample_width * channels
                end_byte = start_byte + chunk_size
                chunk_data = data[start_byte:end_byte]
                if not chunk_data:
                    break

                # Adjust volume
                adjusted_chunk = self.adjust_volume(
                    chunk_data,
                    channels,
                    sample_width
                )

                if self.audio_stream:
                    self.audio_stream.write(adjusted_chunk)
                else:
                    break

                # Update frames played
                frames_in_chunk = len(chunk_data) // (sample_width * channels)
                total_frames_played += frames_in_chunk

                # Update playhead position
                elapsed_time = total_frames_played / sample_rate  # In seconds
                playhead_x = self.playback_start_position + (elapsed_time * self.pixels_per_second)
                self.root.after(0, self.update_playhead_visual, playhead_x)

            # Finish any remaining data
            if self.is_playing:
                remaining_data = data[total_frames_played * sample_width * channels:]
                if remaining_data:
                    adjusted_chunk = self.adjust_volume(
                        remaining_data,
                        channels,
                        sample_width
                    )
                    if self.audio_stream:
                        self.audio_stream.write(adjusted_chunk)

        except Exception as e:
            messagebox.showerror("Error", f"Playback error: {e}")
        finally:
            # Update playhead position to final position if not stopped manually
            if not self.playback_stopped_manually:
                final_playhead_x = self.playback_start_position + (total_frames_played / sample_rate) * self.pixels_per_second
                self.root.after(0, self.update_playhead, final_playhead_x)

            self.is_playing = False
            if self.audio_stream:
                try:
                    self.audio_stream.stop_stream()
                    self.audio_stream.close()
                except Exception:
                    pass
                self.audio_stream = None
            # Reset pause button text
            self.root.after(0, self.pause_button.config, {'text': 'Pause'})
            # Reset play button text to "Play" if playback finished naturally
            if not self.playback_stopped_manually:
                self.root.after(0, self.play_button.config, {'text': 'Play'})
            self.playback_thread = None
            self.playback_stopped_manually = False  # Reset the flag

    def adjust_volume(self, chunk_data, channels, sample_width):
        """Adjust the volume of the audio chunk."""
        # Convert chunk_data to numpy array
        dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[sample_width]
        audio_array = np.frombuffer(chunk_data, dtype=dtype)

        # Handle stereo or mono
        if channels == 2:
            audio_array = np.reshape(audio_array, (-1, 2))

        # Calculate volume factor
        volume_db = self.volume_slider.get()
        volume_factor = 10 ** (volume_db / 20)

        # Adjust volume
        adjusted_array = (audio_array * volume_factor).astype(dtype)

        # Clip values to prevent overflow
        max_value = np.iinfo(dtype).max
        min_value = np.iinfo(dtype).min
        adjusted_array = np.clip(adjusted_array, min_value, max_value)

        # Reshape back if stereo
        if channels == 2:
            adjusted_array = adjusted_array.flatten()

        # Convert back to bytes
        adjusted_chunk = adjusted_array.tobytes()
        return adjusted_chunk

    def update_playhead_visual(self, playhead_x):
        """Update visual playhead position on the canvas."""
        self.timeline_canvas.coords(self.playhead, playhead_x, 0, playhead_x, 500)
        self.ruler_canvas.coords(self.ruler_playhead, playhead_x, 0, playhead_x, 30)
        # Do not update self.playhead_position here

    def update_playhead(self, playhead_x):
        """Update playhead position after playback ends."""
        self.playhead_position = playhead_x
        self.timeline_canvas.coords(self.playhead, playhead_x, 0, playhead_x, 500)
        self.ruler_canvas.coords(self.ruler_playhead, playhead_x, 0, playhead_x, 30)

    def reset_playhead(self):
        """Reset playhead to start."""
        self.playhead_position = 0
        self.timeline_canvas.coords(self.playhead, 0, 0, 0, 500)
        self.ruler_canvas.coords(self.ruler_playhead, 0, 0, 0, 30)

    def pause_audio(self):
        """Pause or resume audio playback."""
        if not self.is_playing:
            return

        if not self.pause_event.is_set():
            self.pause_event.set()
            self.pause_button.config(text="Resume")
        else:
            self.pause_event.clear()
            self.pause_button.config(text="Pause")

    def update_bpm(self, value):
        """Update BPM value and redraw grid and ruler."""
        self.bpm = int(value)
        self.bpm_display.config(text=f"{self.bpm} BPM")
        # Update time mapping
        self.update_time_mapping()
        # Update positions and sizes of clips
        self.update_clips_positions()
        # Redraw grid and ruler based on new BPM
        self.update_scroll_region()

    def update_volume(self, value):
        """Update the volume level."""
        volume_level = int(value)
        print(f"Volume set to: {volume_level} dB")
        # Volume adjustment is now handled in real-time during playback

    def update_division(self, value):
        """Update the grid subdivision and redraw grid and ruler."""
        self.subdivision = self.division_map[value]  # For snapping and grid drawing
        # Redraw grid and ruler
        self.update_scroll_region()

    def mix_audio_clips(self, exporting=False):
        """Mix all audio clips into a single AudioSegment."""
        if not self.audio_clips:
            return None

        # Determine the total duration
        total_duration_ms = self.get_total_duration(exporting=exporting)
        base_sample_rate = 44100  # Standard sample rate
        base_channels = 2  # Stereo
        base_sample_width = 2  # 16 bits

        # Initialize a silent audio segment for the full duration
        combined_audio = AudioSegment.silent(
            duration=total_duration_ms,
            frame_rate=base_sample_rate
        )
        # Set channels and sample width
        combined_audio = combined_audio.set_channels(base_channels)
        combined_audio = combined_audio.set_sample_width(base_sample_width)

        for clip in self.audio_clips:
            # Use stored start_time_seconds
            start_time_ms = clip["start_time_seconds"] * 1000

            # Create an AudioSegment from raw data
            audio_segment = AudioSegment(
                data=clip["raw_data"],
                sample_width=clip["sample_width"],
                frame_rate=clip["frame_rate"],
                channels=clip["channels"]
            )

            # Ensure audio segment is at the base sample rate, channels, and sample width
            if audio_segment.frame_rate != base_sample_rate:
                audio_segment = audio_segment.set_frame_rate(base_sample_rate)
            if audio_segment.channels != base_channels:
                audio_segment = audio_segment.set_channels(base_channels)
            if audio_segment.sample_width != base_sample_width:
                audio_segment = audio_segment.set_sample_width(base_sample_width)

            # Overlay the audio segment onto the combined audio
            combined_audio = combined_audio.overlay(audio_segment, position=start_time_ms)

        return combined_audio

    def get_total_duration(self, exporting=False):
        """Calculate the total duration needed for the combined audio."""
        max_end_time = 0
        for clip in self.audio_clips:
            # Use stored start_time_seconds
            start_time_ms = clip["start_time_seconds"] * 1000

            # Get the duration of the clip
            clip_duration_ms = clip["duration_seconds"] * 1000

            # Calculate end time
            end_time = start_time_ms + clip_duration_ms
            if end_time > max_end_time:
                max_end_time = end_time

        if exporting:
            # For exporting, use the actual max end time
            total_duration_ms = max_end_time
        else:
            # Ensure total duration is at least the initial canvas length (10 minutes)
            total_duration_ms = max(max_end_time, 600000)
        return total_duration_ms

    def delete_selected_clip(self, event):
        """Delete the selected audio clip when backspace is pressed."""
        if hasattr(self, 'selected_clip') and self.selected_clip:
            # Remove graphical elements
            self.timeline_canvas.delete(self.selected_clip["background_id"])
            self.timeline_canvas.delete(self.selected_clip["outline_id"])
            self.timeline_canvas.delete(self.selected_clip["text_id"])
            for line_id in self.selected_clip["waveform_ids"]:
                self.timeline_canvas.delete(line_id)

            # Remove from audio_clips list
            self.audio_clips.remove(self.selected_clip)

            # Clear selected_clip
            self.selected_clip = None

            # Update scroll region
            self.update_scroll_region()

    def export_audio(self):
        """Export the arrangement to an audio file."""
        if not self.audio_clips:
            messagebox.showwarning("Export", "No audio clips to export.")
            return

        # Ask the user where to save the file
        file_path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav"), ("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        if not file_path:
            return  # User cancelled

        # Mix the audio clips
        combined_audio = self.mix_audio_clips(exporting=True)

        if combined_audio is None:
            messagebox.showerror("Export", "Failed to mix audio clips.")
            return

        # Get the earliest start time and latest end time
        earliest_start_ms = min(clip["start_time_seconds"] * 1000 for clip in self.audio_clips)
        latest_end_ms = max((clip["start_time_seconds"] + clip["duration_seconds"]) * 1000 for clip in self.audio_clips)

        # Trim the combined audio to the range
        export_audio = combined_audio[earliest_start_ms:latest_end_ms]

        # Save the audio file
        try:
            export_audio.export(file_path, format=file_path.split('.')[-1])
            messagebox.showinfo("Export", f"Arrangement exported successfully to {file_path}")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export arrangement: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = DAWApp(root)
    root.mainloop()
