import tkinter as tk
from tkinter import filedialog, messagebox
from threading import Event
import threading
import pyaudio
from pydub import AudioSegment
import numpy as np
import random
import time

from constants import BASE_SAMPLE_RATE, BASE_CHANNELS, BASE_SAMPLE_WIDTH
from GUI_config import create_controls, create_timeline
from audio_config import adjust_volume, mix_audio_clips, create_waveform

class DAWApp:
    def __init__(self, root):
        self.root = root
        self.root.title("DAW")
        self.root.geometry("1200x600")
        self.audio_clips = []
        self.current_audio = None
        self.pyaudio_instance = pyaudio.PyAudio()
        self.audio_stream = None
        self.is_playing = False
        self.pause_event = Event()
        self.playback_thread = None
        self.playback_stopped_manually = False 

        self.bpm = 120
        self.beats_per_bar = 4  
        self.subdivision = 1   

        self.pixels_per_second = 100  
        self.update_time_mapping()   

        #playhead pos
        self.playhead_position = 0
        self.playback_start_position = 0

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_controls()
        self.create_timeline()

    def on_close(self):
        #clean up when closed
        self.stop_audio()
        self.pyaudio_instance.terminate()
        self.root.destroy()

    def create_controls(self):
        create_controls(self)

    def create_timeline(self):
        create_timeline(self)

    def xview(self, *args):
        #scroll views
        self.timeline_canvas.xview(*args)
        self.ruler_canvas.xview(*args)

    def update_time_mapping(self):
        self.pixels_per_second = 100 
        self.pixels_per_beat = self.pixels_per_second * 60 / self.bpm
        self.pixels_per_bar = self.pixels_per_beat * self.beats_per_bar

    def draw_ruler(self):
        self.ruler_canvas.delete("all")

        scrollregion = self.ruler_canvas.cget("scrollregion") 
        x0, y0, x1, y1 = map(int, scrollregion.split())

        #ruler markings
        x = 0
        bar_number = 1
        while x <= x1:
            self.ruler_canvas.create_line(x, 0, x, 30, fill="black")
            #Label bar number
            self.ruler_canvas.create_text(x + 2, 2, anchor='nw', text=f"Bar {bar_number}", fill="black", font=("Arial", 8))
            bar_number += 1

            #beat ticks
            beat_x = x + self.pixels_per_beat
            for beat in range(1, self.beats_per_bar):
                self.ruler_canvas.create_line(beat_x, 15, beat_x, 30, fill="black")
                beat_x += self.pixels_per_beat

            x += self.pixels_per_bar

    def draw_grid(self):
        self.timeline_canvas.delete("grid") 

        scrollregion = self.timeline_canvas.cget("scrollregion") 
        x0, y0, x1, y1 = map(int, scrollregion.split())

        #make vertical grid lines
        x = 0
        while x <= x1:
            #bar lines
            self.timeline_canvas.create_line(x, 0, x, y1, fill="black", width=1, tags="grid")
            beat_x = x
            for beat in range(1, self.beats_per_bar + 1):
                beat_x += self.pixels_per_beat
                #beat lines
                if beat <= self.beats_per_bar:
                    self.timeline_canvas.create_line(beat_x, 0, beat_x, y1, fill="grey", dash=(2, 2), tags="grid")
                #subdivisions
                if self.subdivision > 1:
                    subdivision_step = self.pixels_per_beat / self.subdivision
                    subdivision_x = beat_x - self.pixels_per_beat
                    for sub in range(1, self.subdivision):
                        subdivision_x += subdivision_step
                        self.timeline_canvas.create_line(subdivision_x, 0, subdivision_x, y1, fill="lightgrey", dash=(1, 1), tags="grid")
            x += self.pixels_per_bar

        for j in range(0, 500, 100):  
            self.timeline_canvas.create_line(0, j, x1, j, fill="black", width=1, tags="grid")

        self.timeline_canvas.create_line(0, 500, x1, 500, fill="black", width=1, tags="grid")

        for clip in self.audio_clips:
            self.timeline_canvas.tag_raise(clip["background_id"])
            self.timeline_canvas.tag_raise(clip["outline_id"])
            self.timeline_canvas.tag_raise(clip["text_id"])
            for line_id in clip["waveform_ids"]:
                self.timeline_canvas.tag_raise(line_id)
        self.timeline_canvas.tag_raise(self.playhead)

    def move_playhead_click(self, event):
        x = self.ruler_canvas.canvasx(event.x)
        self.set_playhead_position(x)

    def move_playhead_drag(self, event):
        x = self.ruler_canvas.canvasx(event.x)
        self.set_playhead_position(x)

    def set_playhead_position(self, x):
        x = max(0, x)
        self.playhead_position = x
        self.timeline_canvas.coords(self.playhead, x, 0, x, 500)
        self.ruler_canvas.coords(self.ruler_playhead, x, 0, x, 30)

    def import_audio(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Audio Files", "*.wav *.mp3"), ("All files", "*.*")]
        )
        if not file_path:
            return

        try:
            audio = AudioSegment.from_file(file_path)

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
        waveform_y = (track_num - 1) * 100 + 50 

        audio_segment = AudioSegment(
            data=raw_data,
            sample_width=sample_width,
            frame_rate=frame_rate,
            channels=channels
        )

        #set to base sample rate/channels
        audio_segment = audio_segment.set_frame_rate(BASE_SAMPLE_RATE)
        audio_segment = audio_segment.set_channels(BASE_CHANNELS)
        audio_segment = audio_segment.set_sample_width(BASE_SAMPLE_WIDTH)

        raw_data = audio_segment.raw_data
        frame_rate = audio_segment.frame_rate
        channels = audio_segment.channels
        sample_width = audio_segment.sample_width

        duration_ms = len(audio_segment)
        duration_in_seconds = duration_ms / 1000

        clip_width = duration_in_seconds * self.pixels_per_second

        #audio clip background
        color = self.get_random_color()
        background_id = self.timeline_canvas.create_rectangle(
            x_position, waveform_y - 15, x_position + clip_width, waveform_y + 15,
            fill=color, outline="", tags="audio_clip_bg"
        )

        start_time_seconds = x_position / self.pixels_per_second

        #audio clip outline
        outline_id = self.timeline_canvas.create_rectangle(
            x_position, waveform_y - 15, x_position + clip_width, waveform_y + 15, outline="blue", width=2
        )

        filename = file_path.split("/")[-1]
        max_text_width = clip_width - 10 
        if len(filename) * 7 > max_text_width and max_text_width > 0:
            filename = filename[:int(max_text_width / 7) - 3] + "..."

        text_id = self.timeline_canvas.create_text(
            x_position + 5, waveform_y - 25,
            text=f"{filename} ({duration_in_seconds:.2f}s)",
            anchor="w", fill="black"
        )

        waveform_points = create_waveform(raw_data, sample_width, waveform_y, x_position, clip_width)
        waveform_id = self.timeline_canvas.create_line(waveform_points, fill="black", smooth=True)
        waveform_ids = [waveform_id]

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

        self.timeline_canvas.tag_raise(background_id)
        self.timeline_canvas.tag_raise(outline_id)
        self.timeline_canvas.tag_raise(text_id)
        for line_id in waveform_ids:
            self.timeline_canvas.tag_raise(line_id)
        self.timeline_canvas.tag_raise(self.playhead)

        self.update_scroll_region()

    def select_clip(self, event):
        self.selected_clip = None
        for clip in self.audio_clips:
            self.timeline_canvas.itemconfig(clip["outline_id"], outline="blue", width=2)

            x_coords = self.timeline_canvas.coords(clip["outline_id"])
            if x_coords[0] <= self.timeline_canvas.canvasx(event.x) <= x_coords[2] and \
               x_coords[1] <= self.timeline_canvas.canvasy(event.y) <= x_coords[3]:
                self.selected_clip = clip
                self.drag_start_x = self.timeline_canvas.canvasx(event.x)
                self.drag_start_y = self.timeline_canvas.canvasy(event.y)

                #highlight selection
                self.timeline_canvas.itemconfig(clip["outline_id"], outline="red", width=3)
                break

    def move_clip(self, event):
        if not self.selected_clip:
            return

        new_x = self.timeline_canvas.canvasx(event.x)
        new_y = self.timeline_canvas.canvasy(event.y)
        dx = new_x - self.drag_start_x
        dy = new_y - self.drag_start_y

        x_coords = self.timeline_canvas.coords(self.selected_clip["outline_id"])

        #restrict movement on screen
        if x_coords[0] + dx < 0:
            dx = -x_coords[0]

        if x_coords[1] + dy < 0:
            dy = -x_coords[1]
        if x_coords[3] + dy > self.timeline_canvas.canvasy(self.timeline_canvas.winfo_height()):
            dy = self.timeline_canvas.canvasy(self.timeline_canvas.winfo_height()) - x_coords[3]

        #move everytging from the clip
        self.timeline_canvas.move(self.selected_clip["background_id"], dx, dy)
        self.timeline_canvas.move(self.selected_clip["outline_id"], dx, dy)
        self.timeline_canvas.move(self.selected_clip["text_id"], dx, dy)
        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.move(line_id, dx, dy)

        self.drag_start_x = new_x
        self.drag_start_y = new_y

        self.timeline_canvas.tag_raise(self.selected_clip["background_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["outline_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["text_id"])
        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.tag_raise(line_id)
        self.timeline_canvas.tag_raise(self.playhead)

        self.update_scroll_region()

    def snap_clip(self, event):
        if not self.selected_clip:
            return

        x_coords = self.timeline_canvas.coords(self.selected_clip["outline_id"])
        x = x_coords[0]
        y = x_coords[1]

        #snap to track
        subdivision_pixels = self.pixels_per_beat / self.subdivision
        new_x = round(x / subdivision_pixels) * subdivision_pixels
        dx = new_x - x

        new_track = max(1, min(5, round(y / 100) + 1))
        new_y = (new_track - 1) * 100 + 50 - 15
        dy = new_y - y

        #move everything
        self.timeline_canvas.move(self.selected_clip["background_id"], dx, dy)
        self.timeline_canvas.move(self.selected_clip["outline_id"], dx, dy)

        rect_coords = self.timeline_canvas.coords(self.selected_clip["outline_id"])
        text_x = rect_coords[0] + 5
        text_y = rect_coords[1] - 10
        self.timeline_canvas.coords(self.selected_clip["text_id"], text_x, text_y)

        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.move(line_id, dx, dy)

        self.selected_clip["track"] = new_track

        self.selected_clip["x"] = rect_coords[0]
        self.selected_clip["start_time_seconds"] = rect_coords[0] / self.pixels_per_second

        self.timeline_canvas.tag_raise(self.selected_clip["background_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["outline_id"])
        self.timeline_canvas.tag_raise(self.selected_clip["text_id"])
        for line_id in self.selected_clip["waveform_ids"]:
            self.timeline_canvas.tag_raise(line_id)
        self.timeline_canvas.tag_raise(self.playhead)

        self.update_scroll_region()

    def update_clips_positions(self):
        for clip in self.audio_clips:
            x_position = clip["start_time_seconds"] * self.pixels_per_second
            clip_width = clip["duration_seconds"] * self.pixels_per_second
            y1, y2 = self.timeline_canvas.coords(clip["outline_id"])[1], self.timeline_canvas.coords(clip["outline_id"])[3]
            self.timeline_canvas.coords(clip["background_id"], x_position, y1, x_position + clip_width, y2)
            self.timeline_canvas.coords(clip["outline_id"], x_position, y1, x_position + clip_width, y2)
            text_x = x_position + 5
            text_y = y1 - 10
            self.timeline_canvas.coords(clip["text_id"], text_x, text_y)
            waveform_y = (clip["track"] - 1) * 100 + 50  
            for line_id in clip["waveform_ids"]:
                self.timeline_canvas.delete(line_id)
            waveform_points = create_waveform(
                clip["raw_data"],
                clip["sample_width"],
                waveform_y,
                x_position,
                clip_width
            )
            waveform_id = self.timeline_canvas.create_line(waveform_points, fill="black", smooth=True)
            clip["waveform_ids"] = [waveform_id]
            clip["x"] = x_position
            clip["clip_width"] = clip_width

        for clip in self.audio_clips:
            self.timeline_canvas.tag_raise(clip["background_id"])
            self.timeline_canvas.tag_raise(clip["outline_id"])
            self.timeline_canvas.tag_raise(clip["text_id"])
            for line_id in clip["waveform_ids"]:
                self.timeline_canvas.tag_raise(line_id)
        self.timeline_canvas.tag_raise(self.playhead)

    def update_scroll_region(self):
        max_clip_x = 0
        for clip in self.audio_clips:
            x_coords = self.timeline_canvas.coords(clip["outline_id"])
            if x_coords[2] > max_clip_x:
                max_clip_x = x_coords[2]
        total_width = max_clip_x + 100 

        min_total_width = 600 * self.pixels_per_second
        total_width = max(total_width, min_total_width)

        self.timeline_canvas.config(scrollregion=(0, 0, total_width, 500))
        self.ruler_canvas.config(scrollregion=(0, 0, total_width, 30))
        self.draw_ruler()
        self.draw_grid()

    def play_audio(self):
        if self.play_button['text'] == 'Play':
            if self.is_playing:
                self.stop_audio()
            self.is_playing = True
            self.playback_stopped_manually = False  
            self.pause_event.clear()
            self.pause_button.config(text="Pause")  
            self.play_button.config(text="Restart")  
            self.playback_start_position = self.playhead_position
            self.playback_thread = threading.Thread(target=self._play_clips)
            self.playback_thread.start()
        elif self.play_button['text'] == 'Restart':
            if self.is_playing:
                self.stop_audio()
                if self.playback_thread and self.playback_thread.is_alive():
                    self.playback_thread.join()
                    self.playback_thread = None
            self.reset_playhead()
            self.play_button.config(text="Play")  

    def stop_audio(self):
        self.is_playing = False
        self.pause_event.clear()
        self.playback_stopped_manually = True  
        if self.playback_thread and self.playback_thread.is_alive():
            self.playback_thread.join(timeout=1)
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except Exception:
                pass
            self.audio_stream = None
        self.pause_button.config(text="Pause")
        self.playback_thread = None
        self.play_button.config(text="Play")

    def _play_clips(self):
        total_duration_ms = self.get_total_duration()
        combined_audio = mix_audio_clips(self.audio_clips, total_duration_ms)

        if combined_audio is None:
            self.is_playing = False
            return

        start_time_ms = (self.playback_start_position / self.pixels_per_second) * 1000

        if start_time_ms >= len(combined_audio):
            messagebox.showinfo("Playback", "Playhead is out of bounds")
            self.is_playing = False
            return

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

            chunk_frames = 1024  
            chunk_size = chunk_frames * sample_width * channels 
            total_frames_played = 0
            total_frames = len(data) // (sample_width * channels)

            while total_frames_played < total_frames and self.is_playing:
                if self.pause_event.is_set():
                    while self.pause_event.is_set() and self.is_playing:
                        time.sleep(0.1)
                start_byte = total_frames_played * sample_width * channels
                end_byte = start_byte + chunk_size
                chunk_data = data[start_byte:end_byte]
                if not chunk_data:
                    break

                volume_db = self.volume_slider.get()
                adjusted_chunk = adjust_volume(
                    chunk_data,
                    channels,
                    sample_width,
                    volume_db
                )

                if self.audio_stream:
                    self.audio_stream.write(adjusted_chunk)
                else:
                    break

                frames_in_chunk = len(chunk_data) // (sample_width * channels)
                total_frames_played += frames_in_chunk

                elapsed_time = total_frames_played / sample_rate 
                playhead_x = self.playback_start_position + (elapsed_time * self.pixels_per_second)
                self.root.after(0, self.update_playhead_visual, playhead_x)

            if self.is_playing:
                remaining_data = data[total_frames_played * sample_width * channels:]
                if remaining_data:
                    volume_db = self.volume_slider.get()
                    adjusted_chunk = adjust_volume(
                        remaining_data,
                        channels,
                        sample_width,
                        volume_db
                    )
                    if self.audio_stream:
                        self.audio_stream.write(adjusted_chunk)

        except Exception as e:
            messagebox.showerror("Error", f"Playback error: {e}")
        finally:
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
            self.root.after(0, self.pause_button.config, {'text': 'Pause'})
            if not self.playback_stopped_manually:
                self.root.after(0, self.play_button.config, {'text': 'Play'})
            self.playback_thread = None
            self.playback_stopped_manually = False  

    def update_playhead_visual(self, playhead_x):
        """Update visual playhead position on the canvas."""
        self.timeline_canvas.coords(self.playhead, playhead_x, 0, playhead_x, 500)
        self.ruler_canvas.coords(self.ruler_playhead, playhead_x, 0, playhead_x, 30)

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
        self.bpm = int(value)
        self.bpm_display.config(text=f"{self.bpm} BPM")
        self.update_time_mapping()
        self.update_clips_positions()
        self.update_scroll_region()

    def update_volume(self, value):
        volume_level = int(value)
        print(f"Volume set to: {volume_level} dB")

    def update_division(self, value):
        self.subdivision = self.division_map[value] 
        self.update_scroll_region()

    def get_total_duration(self):
        max_end_time = 0
        for clip in self.audio_clips:
            start_time_ms = clip["start_time_seconds"] * 1000

            clip_duration_ms = clip["duration_seconds"] * 1000

            #calculate end time
            end_time = start_time_ms + clip_duration_ms
            if end_time > max_end_time:
                max_end_time = end_time

        total_duration_ms = max(max_end_time, 600000)
        return total_duration_ms

    def delete_selected_clip(self, event):
        #delete everything when clicking backspace
        if hasattr(self, 'selected_clip') and self.selected_clip:
            self.timeline_canvas.delete(self.selected_clip["background_id"])
            self.timeline_canvas.delete(self.selected_clip["outline_id"])
            self.timeline_canvas.delete(self.selected_clip["text_id"])
            for line_id in self.selected_clip["waveform_ids"]:
                self.timeline_canvas.delete(line_id)

            self.audio_clips.remove(self.selected_clip)
            self.selected_clip = None
            self.update_scroll_region()

    def export_audio(self):
        if not self.audio_clips:
            messagebox.showwarning("Export", "No audio clips to export.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".wav",
            filetypes=[("WAV files", "*.wav"), ("MP3 files", "*.mp3"), ("All files", "*.*")]
        )
        if not file_path:
            return  

        total_duration_ms = self.get_total_duration()
        combined_audio = mix_audio_clips(self.audio_clips, total_duration_ms)

        if combined_audio is None:
            messagebox.showerror("Export", "Failed to mix audio clips.")
            return

        earliest_start_ms = min(clip["start_time_seconds"] * 1000 for clip in self.audio_clips)
        latest_end_ms = max((clip["start_time_seconds"] + clip["duration_seconds"]) * 1000 for clip in self.audio_clips)

        export_audio = combined_audio[earliest_start_ms:latest_end_ms]

        try:
            export_audio.export(file_path, format=file_path.split('.')[-1])
            messagebox.showinfo("Export", f"Arrangement exported successfully to {file_path}")
        except Exception as e:
            messagebox.showerror("Export", f"Failed to export arrangement: {e}")
