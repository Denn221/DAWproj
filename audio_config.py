import numpy as np
from pydub import AudioSegment
from constants import BASE_SAMPLE_RATE, BASE_CHANNELS, BASE_SAMPLE_WIDTH

def adjust_volume(chunk_data, channels, sample_width, volume_db):
    dtype = {1: np.uint8, 2: np.int16, 4: np.int32}[sample_width]
    audio_array = np.frombuffer(chunk_data, dtype=dtype)

    #stero or mono
    if channels == 2:
        audio_array = np.reshape(audio_array, (-1, 2))

    volume_factor = 10 ** (volume_db / 20)

    #adjust volume
    adjusted_array = (audio_array * volume_factor).astype(dtype)

    max_value = np.iinfo(dtype).max
    min_value = np.iinfo(dtype).min
    adjusted_array = np.clip(adjusted_array, min_value, max_value)

    if channels == 2:
        adjusted_array = adjusted_array.flatten()

    adjusted_chunk = adjusted_array.tobytes()
    return adjusted_chunk

def mix_audio_clips(audio_clips, total_duration_ms):
    if not audio_clips:
        return None

    combined_audio = AudioSegment.silent(
        duration=total_duration_ms,
        frame_rate=BASE_SAMPLE_RATE
    )
    #set channels and sample width
    combined_audio = combined_audio.set_channels(BASE_CHANNELS)
    combined_audio = combined_audio.set_sample_width(BASE_SAMPLE_WIDTH)

    for clip in audio_clips:
        start_time_ms = clip["start_time_seconds"] * 1000

        audio_segment = AudioSegment(
            data=clip["raw_data"],
            sample_width=clip["sample_width"],
            frame_rate=clip["frame_rate"],
            channels=clip["channels"]
        )

        if audio_segment.frame_rate != BASE_SAMPLE_RATE:
            audio_segment = audio_segment.set_frame_rate(BASE_SAMPLE_RATE)
        if audio_segment.channels != BASE_CHANNELS:
            audio_segment = audio_segment.set_channels(BASE_CHANNELS)
        if audio_segment.sample_width != BASE_SAMPLE_WIDTH:
            audio_segment = audio_segment.set_sample_width(BASE_SAMPLE_WIDTH)

        combined_audio = combined_audio.overlay(audio_segment, position=start_time_ms)

    return combined_audio

def create_waveform(raw_data, sample_width, y_offset, x_offset, clip_width, max_points=2000):
    audio_array = np.frombuffer(raw_data, dtype=np.int16)
    max_height = 20

    num_points = min(int(clip_width), max_points)
    if num_points <= 1:
        num_points = 2 

    indices = np.linspace(0, len(audio_array) - 1, num=num_points, dtype=int)
    sampled_audio = audio_array[indices]

    max_value = np.max(np.abs(audio_array))
    if max_value == 0:
        max_value = 1 

    x_values = np.linspace(x_offset, x_offset + clip_width, num=num_points)
    y_values = y_offset - (sampled_audio / max_value) * max_height

    points = []
    for x, y in zip(x_values, y_values):
        points.extend([x, y])

    return points 
