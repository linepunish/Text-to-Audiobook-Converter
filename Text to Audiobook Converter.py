# Original imports (keep these)
import sys
import re
import argparse
import os
import tempfile
import shutil
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk # Added ImageTk
import cv2
from tqdm import tqdm # tqdm progress might not show well in GUI, replaced with status updates
from pydub import AudioSegment
# import pydub.playback # Playback not needed for GUI generation
from pydub.silence import detect_leading_silence
import math
import subprocess

# GUI specific imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font as tkfont
import threading
import queue # For thread communication (optional for advanced progress)

# --- Paste your entire TextToVideo class here ---
class TextToVideo:
    def __init__(self, font_path=None, font_size=40, fps=24, duration_per_sentence=None,
                 transition_duration=0.5, width=1280, height=720,
                 background_color=(0, 0, 0), text_color=(255, 255, 255),
                 tts_engine='balcon', language='en', voice=None, speed=0,
                 balcon_path='balcon.exe', status_callback=None): # Added status_callback
        """
        Initialize the TextToVideo converter with customizable parameters
        """
        self.fps = fps
        self.duration_per_sentence = duration_per_sentence  # If None, will be determined by TTS duration
        self.transition_duration = transition_duration
        self.width = width
        self.height = height
        self.background_color = background_color
        self.text_color = text_color
        self.tts_engine = tts_engine
        self.language = language
        self.voice = voice
        self.speed = speed
        self.temp_dir = None
        self.balcon_path = balcon_path
        self.status_callback = status_callback # Store the callback

        # Find a suitable font (keep original logic)
        if font_path and os.path.exists(font_path):
            self.font_path = font_path
        else:
            if os.name == 'nt':  # Windows
                font_options = [
                    "C:\\Windows\\Fonts\\arial.ttf",
                    "C:\\Windows\\Fonts\\calibri.ttf",
                    "C:\\Windows\\Fonts\\segoeui.ttf"
                ]
            elif os.name == 'posix':  # macOS or Linux
                font_options = [
                    "/System/Library/Fonts/Helvetica.ttc",  # macOS
                    "/System/Library/Fonts/SF-Pro-Text-Regular.otf", # macOS
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Linux
                    "/usr/share/fonts/TTF/Arial.ttf"  # Linux
                ]
            else:
                font_options = []

            found_font = None
            for font in font_options:
                if os.path.exists(font):
                    found_font = font
                    break
            if found_font:
                 self.font_path = found_font
            elif font_path: # If user provided one but it didn't exist
                 self.font_path = font_path # Keep user attempt for error reporting
                 # Let the error happen later if still not found
            else:
                 self.font_path = None # Indicate no default found


        self.font_size = font_size
        # Load font only when needed, handle potential errors there
        self.pil_font = None # Delay loading

    def _load_font(self):
        """Loads the PIL font object, raises error if path is invalid."""
        if self.pil_font is None:
            if not self.font_path or not os.path.exists(self.font_path):
                 raise FileNotFoundError(f"Font file not found or not specified: {self.font_path}")
            try:
                self.pil_font = ImageFont.truetype(self.font_path, self.font_size)
            except IOError as e:
                raise IOError(f"Error loading font '{self.font_path}': {e}")


    def _log_status(self, message):
        """Helper to send status updates via callback if available."""
        # print(message) # Keep console logging if desired
        if self.status_callback:
            self.status_callback(message)

    def split_into_sentences(self, text):
        """
        Split the input text into sentences (keep original logic)
        """
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    def create_frame(self, text, fade=1.0):
        """
        Create a single frame with the given text and fade level (keep original logic, ensure font is loaded)
        """
        self._load_font() # Ensure font is loaded before drawing
        img = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(img)

        # Calculate text position for center alignment (using potentially adjusted font)
        current_font = self.pil_font
        temp_font_size = self.font_size

        # Initial attempt with original font size
        while temp_font_size > 5: # Don't let font get impossibly small
            try:
                current_font = ImageFont.truetype(self.font_path, temp_font_size)
                lines = self._wrap_text(text, current_font)
                total_height = self._calculate_text_block_height(lines, current_font)

                if total_height <= self.height - 40: # Check if it fits vertically with margin
                    break # Font size is okay
                else:
                    temp_font_size = int(temp_font_size * 0.9) # Reduce size and retry
                    self._log_status(f"Text too long, reducing font size to {temp_font_size}...")

            except IOError: # Handle case where smaller font size somehow fails
                 self._log_status(f"Warning: Could not load font at size {temp_font_size}. Using previous.")
                 break # Use the last known good size


        # Apply fade to text color
        text_color = tuple(int(c * fade) for c in self.text_color)

        # Draw the wrapped text
        self._draw_wrapped_text(draw, lines, text_color, current_font)

        return np.array(img)


    def _wrap_text(self, text, font):
        """Helper function to wrap text into lines."""
        words = text.split()
        lines = []
        current_line = []
        max_width = self.width - 100  # Margin

        for word in words:
            test_line_list = current_line + [word]
            test_line = ' '.join(test_line_list)
            try:
                 # Use getbbox for potentially more accurate width in newer Pillow versions
                 left, top, right, bottom = font.getbbox(test_line)
                 width = right - left
            except AttributeError:
                 # Fallback for older Pillow versions
                 width, _ = font.getsize(test_line)


            if width <= max_width:
                current_line.append(word)
            else:
                # Handle word longer than max_width
                if not current_line:
                    # If the single word is too long, just put it on its own line
                    lines.append(word)
                    # Don't reset current_line, it's implicitly handled
                else:
                    # Finish the previous line
                    lines.append(' '.join(current_line))
                    # Start new line with the current word
                    current_line = [word]

        # Add the last line
        if current_line:
            lines.append(' '.join(current_line))

        return lines

    def _calculate_text_block_height(self, lines, font):
        """Calculates the total height of the text block."""
        if not lines:
            return 0

        try:
             # Get height from bounding box for potentially better accuracy
             _, top, _, bottom = font.getbbox('A') # Get height of a character
             line_h = bottom - top
        except AttributeError:
             # Fallback for older Pillow
             _, line_h = font.getsize('A')

        line_spacing_multiplier = 1.4 # Slightly less than 1.5 might look better
        total_height = line_h * len(lines) * line_spacing_multiplier
        return total_height

    def _draw_wrapped_text(self, draw, lines, text_color, font):
        """Draws the already wrapped lines of text centered."""
        if not lines:
            return

        try:
             _, top, _, bottom = font.getbbox('A')
             line_h = bottom - top
        except AttributeError:
             _, line_h = font.getsize('A')

        line_spacing_multiplier = 1.4
        line_height_pixels = line_h * line_spacing_multiplier
        total_height = line_height_pixels * len(lines)

        # Start drawing from top-center
        y = (self.height - total_height) // 2

        for line in lines:
            try:
                left, _, right, _ = font.getbbox(line)
                width = right - left
            except AttributeError:
                width, _ = font.getsize(line)

            x = (self.width - width) // 2
            draw.text((x, y), line, font=font, fill=text_color)
            y += line_height_pixels


    def generate_speech_balcon(self, sentences):
        """
        Generate speech using Balabolka (keep original logic, add status updates)
        """
        if not os.path.exists(self.balcon_path):
             raise FileNotFoundError(f"Balabolka command line tool not found at: {self.balcon_path}")

        self.temp_dir = tempfile.mkdtemp()
        audio_files = []
        durations = []

        self._log_status(f"Generating speech for {len(sentences)} sentences using Balabolka...")
        # Use range for index tracking without tqdm in GUI
        for i in range(len(sentences)):
            sentence = sentences[i]
            self._log_status(f"  Processing sentence {i+1}/{len(sentences)}: '{sentence[:30]}...'")
            output_file = os.path.join(self.temp_dir, f"sentence_{i}.wav")
            text_file = os.path.join(self.temp_dir, f"sentence_{i}.txt")

            try:
                with open(text_file, 'w', encoding='utf-8') as f:
                    f.write(sentence)

                cmd = [self.balcon_path]
                cmd.extend(['-f', text_file])
                cmd.extend(['-w', output_file])
                if self.voice:
                    cmd.extend(['-n', self.voice])
                cmd.extend(['-s', str(self.speed)])
                # Use utf8 encoding for input text file
                cmd.extend(['--encoding', 'utf8'])
                # Suppress Balcon's own console output if possible (might vary by version)
                # Add '-silent' or similar flags if supported by your balcon version
                # cmd.append('-silent') # Example, check balcon documentation

                # Run Balcon
                result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
                # Note: Balcon might output its own progress/status to stdout/stderr
                # self._log_status(f"Balcon stdout: {result.stdout}") # Optional: log balcon output
                # if result.stderr: self._log_status(f"Balcon stderr: {result.stderr}")

            except subprocess.CalledProcessError as e:
                error_message = f"Error executing balcon: {e}\n"
                error_message += f"Command: {' '.join(cmd)}\n"
                error_message += f"Balcon stdout: {e.stdout}\n"
                error_message += f"Balcon stderr: {e.stderr}\n"
                self._log_status(error_message) # Log error details
                raise RuntimeError(f"Balabolka (balcon) failed for sentence {i+1}. Check logs/console.") from e
            except Exception as e:
                 self._log_status(f"Error during speech generation for sentence {i+1}: {e}")
                 raise # Re-raise other exceptions
            finally:
                if os.path.exists(text_file):
                    os.remove(text_file)

            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                 raise FileNotFoundError(f"Balcon ran but failed to create a valid audio file: {output_file}")

            # Load audio and calculate duration
            try:
                 audio = AudioSegment.from_wav(output_file)
                 duration_sec = len(audio) / 1000.0
                 # Add a tiny buffer to duration to prevent issues with exact timing
                 durations.append(duration_sec + 0.05)
                 audio_files.append(output_file)
            except Exception as e:
                 self._log_status(f"Error loading generated wav file {output_file}: {e}")
                 raise RuntimeError(f"Could not process generated audio for sentence {i+1}.") from e

        self._log_status("Speech generation complete.")
        return audio_files, durations

    def create_silent_audio_segment(self, duration_ms):
        """
        Create a silent audio segment (keep original logic)
        """
        return AudioSegment.silent(duration=duration_ms)

    def create_synchronized_audio(self, audio_files, display_timings):
        """
        Create a synchronized audio track (keep original logic, add status)
        """
        self._log_status("Creating synchronized audio track...")
        combined_audio = AudioSegment.empty()
        current_position_ms = 0

        for i, (audio_file, (start_time, end_time)) in enumerate(zip(audio_files, display_timings)):
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            display_duration_ms = end_ms - start_ms

            try:
                speech = AudioSegment.from_file(audio_file)
                speech_duration_ms = len(speech)

                # Add silence buffer to reach the start time
                if start_ms > current_position_ms:
                    silence_duration = start_ms - current_position_ms
                    silence = self.create_silent_audio_segment(silence_duration)
                    combined_audio += silence
                    current_position_ms = start_ms

                target_speech_duration_ms = display_duration_ms - int(self.transition_duration * 2 * 1000)
                if target_speech_duration_ms <= 0:
                     self._log_status(f"Warning: Display duration too short for transitions for sentence {i+1}. Audio might be cut short.")
                     target_speech_duration_ms = 10 # Use a tiny duration


                # Adjust speed if needed (slightly different logic for fitting within display minus transitions)
                if speech_duration_ms > target_speech_duration_ms:
                    speed_factor = speech_duration_ms / target_speech_duration_ms
                    self._log_status(f"  Adjusting speed for sentence {i+1} (Factor: {speed_factor:.2f})")
                    try:
                        # pydub > 0.25.0 uses speedup
                        speech = speech.speedup(playback_speed=speed_factor)
                        # Ensure frame rate is standard after potential speedup changes
                        speech = speech.set_frame_rate(44100)
                    except AttributeError:
                         # Older pydub version fallback (less accurate)
                         self._log_status("  (Using older pydub speed adjustment method)")
                         new_frame_rate = int(speech.frame_rate * speed_factor)
                         speech = speech._spawn(speech.raw_data, overrides={"frame_rate": new_frame_rate})
                         speech = speech.set_frame_rate(44100) # Reset frame rate


                elif speech_duration_ms < target_speech_duration_ms:
                     # Add padding silence if speech is shorter than the available slot
                     padding_needed = target_speech_duration_ms - speech_duration_ms
                     speech += self.create_silent_audio_segment(padding_needed)


                combined_audio += speech
                current_position_ms += len(speech) # Actual duration added

                # Add silence equivalent to fade-out transition before next sentence starts
                transition_silence_ms = int(self.transition_duration * 1000)
                combined_audio += self.create_silent_audio_segment(transition_silence_ms)
                current_position_ms += transition_silence_ms


            except Exception as e:
                self._log_status(f"Error processing audio for sentence {i+1} ({audio_file}): {e}")
                # Decide whether to continue or raise. Let's try to continue.
                # Add silence for the expected duration if processing fails
                display_duration_ms = int((end_time - start_time) * 1000)
                if display_duration_ms > 0:
                     combined_audio += self.create_silent_audio_segment(display_duration_ms)
                     current_position_ms += display_duration_ms


        combined_audio_path = os.path.join(self.temp_dir, "synchronized_audio.wav")
        try:
            combined_audio.export(combined_audio_path, format="wav")
            self._log_status("Synchronized audio track created.")
        except Exception as e:
             self._log_status(f"Error exporting combined audio: {e}")
             raise RuntimeError("Failed to export combined audio.") from e

        return combined_audio_path


    def combine_audio_video(self, final_output_path, audio_path, temp_video_path):
        """
        Combine video and audio using ffmpeg (keep original logic, add status)
        """
        self._log_status("Combining video and audio using ffmpeg...")

        # Ensure ffmpeg is available (basic check)
        try:
            subprocess.run(['ffmpeg', '-version'], check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            self._log_status("Error: ffmpeg command not found or failed. Please ensure ffmpeg is installed and in your system's PATH.")
            raise RuntimeError("ffmpeg is required but not found.") from e

        # Use -map options for clarity and robustness
        cmd = [
            'ffmpeg',
            '-i', temp_video_path,     # Input video
            '-i', audio_path,          # Input audio
            '-map', '0:v:0',           # Map video stream from first input
            '-map', '1:a:0',           # Map audio stream from second input
            '-c:v', 'copy',            # Copy video stream without re-encoding
            '-c:a', 'aac',             # Encode audio to AAC (common standard)
            '-b:a', '192k',            # Set audio bitrate
            '-shortest',               # Finish encoding when the shortest input stream ends
            '-y',                      # Overwrite output file without asking
            final_output_path
        ]

        try:
            # Use subprocess.run for better error capture
            result = subprocess.run(cmd, check=True, capture_output=True, text=True, encoding='utf-8', errors='ignore')
            # self._log_status(f"ffmpeg stdout:\n{result.stdout}") # Optional: log ffmpeg output
            # if result.stderr: self._log_status(f"ffmpeg stderr:\n{result.stderr}") # ffmpeg often logs progress to stderr
            self._log_status(f"Video with audio saved successfully as {final_output_path}")
        except subprocess.CalledProcessError as e:
            error_message = f"Error executing ffmpeg: {e}\n"
            error_message += f"Command: {' '.join(cmd)}\n"
            error_message += f"ffmpeg stdout:\n{e.stdout}\n"
            error_message += f"ffmpeg stderr:\n{e.stderr}\n"
            self._log_status(error_message) # Log error details
            # Attempt to provide a more specific error if possible
            if "Permission denied" in e.stderr:
                 raise RuntimeError(f"ffmpeg failed. Permission denied writing to '{final_output_path}'. Check file/folder permissions.") from e
            elif "No such file or directory" in e.stderr:
                 raise RuntimeError(f"ffmpeg failed. Input file missing (video: '{temp_video_path}', audio: '{audio_path}') or ffmpeg path issue.") from e
            else:
                 raise RuntimeError(f"ffmpeg failed while combining audio/video. Check logs/console for details.") from e
        except Exception as e:
             self._log_status(f"An unexpected error occurred during ffmpeg execution: {e}")
             raise


    def cleanup(self):
        """
        Clean up temporary files (keep original logic, add status)
        """
        if self.temp_dir and os.path.exists(self.temp_dir):
            self._log_status(f"Cleaning up temporary directory: {self.temp_dir}")
            try:
                shutil.rmtree(self.temp_dir)
                self.temp_dir = None
                self._log_status("Cleanup complete.")
            except Exception as e:
                self._log_status(f"Warning: Failed to completely remove temporary directory {self.temp_dir}: {e}")


    def generate_video(self, sentences, output_path):
        """
        Generate video (main process, keep logic, integrate status updates, use instance vars)
        """
        video = None # Initialize video writer variable
        try:
            # 1. Generate Speech
            if self.tts_engine == 'balcon':
                audio_files, speech_durations = self.generate_speech_balcon(sentences)
            else:
                raise ValueError(f"Unsupported TTS engine: {self.tts_engine}")

            # 2. Calculate Timings
            self._log_status("Calculating display timings...")
            display_durations = []
            display_timings = []
            current_time = 0
            transition_sec = self.transition_duration

            for i, speech_dur in enumerate(speech_durations):
                 # Duration = speech + fade_in + fade_out
                 base_duration = speech_dur + (transition_sec * 2)

                 # Apply fixed duration if specified and longer
                 if self.duration_per_sentence is not None:
                     sentence_duration = max(base_duration, self.duration_per_sentence)
                 else:
                     sentence_duration = base_duration

                 # Ensure minimum duration to accommodate transitions
                 min_duration_for_transitions = transition_sec * 2 + 0.1 # Add small buffer
                 sentence_duration = max(sentence_duration, min_duration_for_transitions)


                 display_durations.append(sentence_duration)

                 start_time = current_time
                 end_time = start_time + sentence_duration
                 display_timings.append((start_time, end_time))
                 current_time = end_time # Next sentence starts immediately after the previous one ends
                 self._log_status(f"  Sentence {i+1}: Display {start_time:.2f}s - {end_time:.2f}s (Duration: {sentence_duration:.2f}s)")


            # 3. Prepare Video Writer
            # Ensure temp_dir exists (should be created by generate_speech)
            if not self.temp_dir or not os.path.exists(self.temp_dir):
                 # This case shouldn't happen if speech gen worked, but handle defensively
                 self.temp_dir = tempfile.mkdtemp()
                 self._log_status(f"Created temporary directory: {self.temp_dir}")

            temp_video_path = os.path.join(self.temp_dir, "temp_video_no_audio.mp4")
            self._log_status(f"Preparing video writer for: {temp_video_path}")

            fourcc = cv2.VideoWriter_fourcc(*'mp4v') # Standard codec
            video = cv2.VideoWriter(temp_video_path, fourcc, self.fps, (self.width, self.height))

            if not video.isOpened():
                 raise IOError(f"Error: Could not open video writer for path {temp_video_path}. Check permissions and codec support.")

            # 4. Generate Frames
            total_frames_estimate = sum(int(self.fps * d) for d in display_durations)
            self._log_status(f"Generating video frames (estimated {total_frames_estimate} frames)...")
            frame_count = 0
            transition_frames = max(1, int(self.fps * transition_sec)) # Ensure at least 1 frame

            for i, sentence in enumerate(sentences):
                 self._log_status(f"  Generating frames for sentence {i+1}/{len(sentences)}")
                 display_duration = display_durations[i]
                 total_sentence_frames = int(self.fps * display_duration)

                 # Ensure frames calculation is robust
                 hold_frames = max(0, total_sentence_frames - 2 * transition_frames)

                 # Fade In
                 for j in range(transition_frames):
                     fade_level = (j + 1) / transition_frames
                     frame = self.create_frame(sentence, fade=fade_level)
                     video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                     frame_count += 1
                     if frame_count % self.fps == 0: # Update status roughly every second
                         self._log_status(f"    ...frame {frame_count}/{total_frames_estimate} (Fade In)")


                 # Hold (Full Visibility)
                 if hold_frames > 0:
                     frame = self.create_frame(sentence, fade=1.0) # Create once
                     for _ in range(hold_frames):
                         video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                         frame_count += 1
                         if frame_count % self.fps == 0:
                              self._log_status(f"    ...frame {frame_count}/{total_frames_estimate} (Hold)")


                 # Fade Out
                 for j in range(transition_frames):
                     fade_level = 1.0 - ((j + 1) / transition_frames)
                     frame = self.create_frame(sentence, fade=fade_level)
                     video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                     frame_count += 1
                     if frame_count % self.fps == 0:
                          self._log_status(f"    ...frame {frame_count}/{total_frames_estimate} (Fade Out)")


                 # Ensure exact number of frames per sentence (handle rounding)
                 while frame_count < sum(int(self.fps * d) for d in display_durations[:i+1]):
                      # Add filler frames if needed (use last fade-out frame)
                      if 'frame' not in locals(): # Handle case where transitions cover everything
                           frame = self.create_frame(sentence, fade=0.0)
                      video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                      frame_count += 1
                      self._log_status(f"    ...adding filler frame {frame_count}")


            self._log_status(f"Finished generating {frame_count} frames.")
            video.release()
            video = None # Indicate release
            self._log_status("Temporary video file created.")

            # 5. Create Synchronized Audio
            synchronized_audio_path = self.create_synchronized_audio(audio_files, display_timings)

            # 6. Combine Audio and Video
            self.combine_audio_video(output_path, synchronized_audio_path, temp_video_path)

            self._log_status("Video generation process completed successfully!")

        except Exception as e:
            self._log_status(f"ERROR during video generation: {e}")
            import traceback
            self._log_status(f"Traceback:\n{traceback.format_exc()}")
            # Re-raise the exception so the calling GUI thread knows it failed
            raise
        finally:
            # Ensure video writer is released if an error occurred mid-generation
            if video is not None and video.isOpened():
                 self._log_status("Releasing video writer due to error or completion...")
                 video.release()
            # Ensure cleanup happens regardless of success or failure
            self.cleanup()
# --- End of TextToVideo class ---


# --- Helper function from original script ---
def list_balcon_voices(balcon_path):
    """
    Get a list of available voices from Balabolka (keep original logic)
    """
    if not os.path.exists(balcon_path):
        # print(f"Balcon path not found for listing voices: {balcon_path}")
        return [] # Return empty list if path invalid

    try:
        # Use text=True and capture_output for cleaner handling
        result = subprocess.run([balcon_path, '-l'],
                                check=True, # Raise error if balcon fails
                                capture_output=True,
                                text=True,
                                encoding='utf-8', # Explicitly set encoding
                                errors='ignore') # Ignore potential decoding errors
        voices = []

        # Filter out empty lines and potential headers/footers
        for line in result.stdout.splitlines():
             line = line.strip()
             # Add basic filtering, adjust if Balcon output format differs
             if line and not line.startswith("---") and not line.lower().startswith("available"):
                  voices.append(line)

        return voices
    except FileNotFoundError:
         # print(f"Error: Balcon executable not found at '{balcon_path}' when listing voices.")
         return [] # Indicate error by returning empty list
    except subprocess.CalledProcessError as e:
        # print(f"Error getting voices from Balcon: {e}")
        # print(f"Balcon stderr: {e.stderr}")
        return [] # Indicate error
    except Exception as e:
        # print(f"An unexpected error occurred while listing voices: {e}")
        return [] # Indicate error


# --- Tkinter GUI Application ---
class TextToVideoApp:
    def __init__(self, master):
        self.master = master
        master.title("Text to Video Converter")
        # Make window slightly larger
        master.geometry("800x750")

        # Style for ttk widgets
        self.style = ttk.Style()
        self.style.theme_use('clam') # Or 'alt', 'default', 'classic'

        # --- Variables ---
        self.input_text = tk.StringVar()
        self.output_path = tk.StringVar(value="output.mp4")
        self.font_path = tk.StringVar()
        self.font_size = tk.IntVar(value=40)
        self.fps = tk.IntVar(value=24)
        self.use_fixed_duration = tk.BooleanVar(value=False)
        self.fixed_duration = tk.DoubleVar(value=5.0) # Default if checkbox is ticked
        self.transition_duration = tk.DoubleVar(value=0.5)
        self.width = tk.IntVar(value=1280)
        self.height = tk.IntVar(value=720)
        self.bg_color_rgb = (0, 0, 0)
        self.bg_color_hex = "#000000"
        self.text_color_rgb = (255, 255, 255)
        self.text_color_hex = "#ffffff"
        self.tts_engine = tk.StringVar(value="balcon") # Only option for now
        self.balcon_path = tk.StringVar(value=self._find_default_balcon())
        self.balcon_voices = []
        self.selected_voice = tk.StringVar()
        self.speed = tk.IntVar(value=0)
        self.is_generating = False # Flag to prevent multiple generations

        # --- GUI Layout ---
        main_frame = ttk.Frame(master, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Configure grid columns
        main_frame.columnconfigure(1, weight=1)

        # --- Input Text ---
        row_idx = 0
        ttk.Label(main_frame, text="Input Text:").grid(row=row_idx, column=0, sticky="nw", pady=2)
        self.text_input_area = tk.Text(main_frame, height=10, width=60, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1)
        self.text_input_area.grid(row=row_idx, column=1, columnspan=2, sticky="ew", pady=2)
        # Scrollbar for text area
        text_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.text_input_area.yview)
        text_scrollbar.grid(row=row_idx, column=3, sticky="ns")
        self.text_input_area['yscrollcommand'] = text_scrollbar.set

        row_idx += 1
        load_button = ttk.Button(main_frame, text="Load Text from File...", command=self.load_text_file)
        load_button.grid(row=row_idx, column=1, columnspan=2, sticky="w", pady=5)

        # --- Output File ---
        row_idx += 1
        ttk.Label(main_frame, text="Output Video File:").grid(row=row_idx, column=0, sticky="w", pady=2)
        output_entry = ttk.Entry(main_frame, textvariable=self.output_path, width=50)
        output_entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 5))
        output_button = ttk.Button(main_frame, text="Browse...", command=self.browse_output_file)
        output_button.grid(row=row_idx, column=2, sticky="w")

        # --- Settings Sections ---
        row_idx += 1
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=row_idx, column=0, columnspan=4, sticky="nsew", pady=10)
        main_frame.rowconfigure(row_idx, weight=1) # Allow notebook to expand

        video_frame = ttk.Frame(notebook, padding="10")
        audio_frame = ttk.Frame(notebook, padding="10")
        text_style_frame = ttk.Frame(notebook, padding="10")

        notebook.add(video_frame, text=' Video Settings ')
        notebook.add(text_style_frame, text=' Text & Style ')
        notebook.add(audio_frame, text=' Audio (TTS) Settings ')

        # --- Video Settings Frame ---
        vf_row = 0
        video_frame.columnconfigure(1, weight=1)
        video_frame.columnconfigure(3, weight=1)

        ttk.Label(video_frame, text="Width:").grid(row=vf_row, column=0, sticky="w", pady=3)
        ttk.Spinbox(video_frame, from_=100, to=7680, textvariable=self.width, width=8).grid(row=vf_row, column=1, sticky="w", pady=3)

        ttk.Label(video_frame, text="Height:").grid(row=vf_row, column=2, sticky="w", padx=(10,0), pady=3)
        ttk.Spinbox(video_frame, from_=100, to=4320, textvariable=self.height, width=8).grid(row=vf_row, column=3, sticky="w", pady=3)

        vf_row += 1
        ttk.Label(video_frame, text="FPS:").grid(row=vf_row, column=0, sticky="w", pady=3)
        ttk.Spinbox(video_frame, from_=1, to=120, textvariable=self.fps, width=8).grid(row=vf_row, column=1, sticky="w", pady=3)

        ttk.Label(video_frame, text="Transition (s):").grid(row=vf_row, column=2, sticky="w", padx=(10,0), pady=3)
        ttk.Spinbox(video_frame, from_=0.0, to=10.0, increment=0.1, format="%.1f", textvariable=self.transition_duration, width=8).grid(row=vf_row, column=3, sticky="w", pady=3)

        vf_row += 1
        self.fixed_dur_check = ttk.Checkbutton(video_frame, text="Fixed Duration/Sentence:", variable=self.use_fixed_duration, command=self.toggle_fixed_duration)
        self.fixed_dur_check.grid(row=vf_row, column=0, columnspan=2, sticky="w", pady=3)
        self.fixed_dur_spinbox = ttk.Spinbox(video_frame, from_=0.1, to=300.0, increment=0.1, format="%.1f", textvariable=self.fixed_duration, width=8, state=tk.DISABLED)
        self.fixed_dur_spinbox.grid(row=vf_row, column=2, columnspan=2, sticky="w", pady=3)


        # --- Text & Style Settings Frame ---
        tsf_row = 0
        text_style_frame.columnconfigure(1, minsize=150) # Give space for font path
        text_style_frame.columnconfigure(3, weight=1)

        ttk.Label(text_style_frame, text="Font File:").grid(row=tsf_row, column=0, sticky="w", pady=3)
        ttk.Entry(text_style_frame, textvariable=self.font_path, width=40).grid(row=tsf_row, column=1, sticky="ew", padx=(0, 5))
        ttk.Button(text_style_frame, text="Browse...", command=self.browse_font_file).grid(row=tsf_row, column=2, sticky="w")

        tsf_row += 1
        ttk.Label(text_style_frame, text="Font Size:").grid(row=tsf_row, column=0, sticky="w", pady=3)
        ttk.Spinbox(text_style_frame, from_=8, to=200, textvariable=self.font_size, width=8).grid(row=tsf_row, column=1, sticky="w", pady=3)

        tsf_row += 1
        ttk.Label(text_style_frame, text="Text Color:").grid(row=tsf_row, column=0, sticky="w", pady=3)
        self.text_color_button = tk.Button(text_style_frame, text="Choose...", command=self.choose_text_color, width=10, relief=tk.GROOVE)
        self.text_color_button.grid(row=tsf_row, column=1, sticky="w", pady=3)
        self.text_color_preview = tk.Label(text_style_frame, text="  ", background=self.text_color_hex, relief=tk.SUNKEN, borderwidth=1)
        self.text_color_preview.grid(row=tsf_row, column=2, sticky="w", padx=5)
        self._update_color_preview(self.text_color_preview, self.text_color_hex) # Initial color

        tsf_row += 1
        ttk.Label(text_style_frame, text="Background Color:").grid(row=tsf_row, column=0, sticky="w", pady=3)
        self.bg_color_button = tk.Button(text_style_frame, text="Choose...", command=self.choose_bg_color, width=10, relief=tk.GROOVE)
        self.bg_color_button.grid(row=tsf_row, column=1, sticky="w", pady=3)
        self.bg_color_preview = tk.Label(text_style_frame, text="  ", background=self.bg_color_hex, relief=tk.SUNKEN, borderwidth=1)
        self.bg_color_preview.grid(row=tsf_row, column=2, sticky="w", padx=5)
        self._update_color_preview(self.bg_color_preview, self.bg_color_hex) # Initial color


        # --- Audio (TTS) Settings Frame ---
        af_row = 0
        audio_frame.columnconfigure(1, weight=1) # Allow path entry to expand

        ttk.Label(audio_frame, text="TTS Engine:").grid(row=af_row, column=0, sticky="w", pady=3)
        # For now, only Balcon is supported
        ttk.Combobox(audio_frame, textvariable=self.tts_engine, values=["balcon"], state="readonly", width=15).grid(row=af_row, column=1, sticky="w", pady=3)

        af_row += 1
        ttk.Label(audio_frame, text="Balcon Path:").grid(row=af_row, column=0, sticky="w", pady=3)
        ttk.Entry(audio_frame, textvariable=self.balcon_path, width=50).grid(row=af_row, column=1, sticky="ew", padx=(0, 5))
        ttk.Button(audio_frame, text="Browse...", command=self.browse_balcon_path).grid(row=af_row, column=2, sticky="w")

        af_row += 1
        ttk.Label(audio_frame, text="Voice:").grid(row=af_row, column=0, sticky="w", pady=3)
        self.voice_combo = ttk.Combobox(audio_frame, textvariable=self.selected_voice, state="readonly", width=35)
        self.voice_combo.grid(row=af_row, column=1, sticky="w", pady=3)
        ttk.Button(audio_frame, text="Refresh Voices", command=self.update_voices_list).grid(row=af_row, column=2, sticky="w", padx=5)

        af_row += 1
        ttk.Label(audio_frame, text="Speech Speed (-10 to +10):").grid(row=af_row, column=0, sticky="w", pady=3)
        ttk.Scale(audio_frame, from_=-10, to=10, variable=self.speed, orient=tk.HORIZONTAL, length=200, command=lambda v: self.speed.set(int(float(v)))).grid(row=af_row, column=1, columnspan=2, sticky="ew", pady=3)
        speed_label = ttk.Label(audio_frame, textvariable=self.speed, width=4) # Display current speed value
        speed_label.grid(row=af_row, column=3, sticky="w", padx=5)


        # --- Action Button ---
        row_idx += 1
        self.generate_button = ttk.Button(main_frame, text="Generate Video", command=self.start_generation)
        self.generate_button.grid(row=row_idx, column=1, columnspan=2, pady=15)

        # --- Status Area ---
        row_idx += 1
        ttk.Label(main_frame, text="Status:").grid(row=row_idx, column=0, sticky="nw", pady=(5,0))
        self.status_area = tk.Text(main_frame, height=8, width=60, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1, state=tk.DISABLED)
        self.status_area.grid(row=row_idx, column=1, columnspan=2, sticky="ew", pady=(5,0))
        # Scrollbar for status area
        status_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.status_area.yview)
        status_scrollbar.grid(row=row_idx, column=3, sticky="ns", pady=(5,0))
        self.status_area['yscrollcommand'] = status_scrollbar.set

        # --- Initial setup ---
        self.update_voices_list() # Try to populate voices on startup
        self.log_status("GUI Initialized. Ready.")
        # Set focus to text input initially
        self.text_input_area.focus_set()

    # --- GUI Action Methods ---

    def _find_default_balcon(self):
        """Attempts to find balcon.exe in common locations."""
        paths_to_check = [
            'balcon.exe', # Current dir or PATH
            'C:\\Program Files (x86)\\Balabolka\\balcon.exe',
            'C:\\Program Files\\Balabolka\\balcon.exe',
            # Add Linux/Mac paths if relevant, though balcon is Windows
        ]
        for path in paths_to_check:
            if os.path.exists(path):
                return os.path.abspath(path)
        return 'balcon.exe' # Default if not found

    def toggle_fixed_duration(self):
        if self.use_fixed_duration.get():
            self.fixed_dur_spinbox.config(state=tk.NORMAL)
        else:
            self.fixed_dur_spinbox.config(state=tk.DISABLED)

    def load_text_file(self):
        filepath = filedialog.askopenfilename(
            title="Open Text File",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            self.text_input_area.delete('1.0', tk.END) # Clear existing text
            self.text_input_area.insert(tk.END, content)
            self.log_status(f"Loaded text from: {filepath}")
        except Exception as e:
            messagebox.showerror("Error Reading File", f"Could not read file:\n{e}")
            self.log_status(f"Error loading file: {e}")

    def browse_output_file(self):
        filepath = filedialog.asksaveasfilename(
            title="Save Video As",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")],
            defaultextension=".mp4",
            initialfile=os.path.basename(self.output_path.get()) # Suggest current name
        )
        if filepath:
            self.output_path.set(filepath)
            self.log_status(f"Output path set to: {filepath}")

    def browse_font_file(self):
        filepath = filedialog.askopenfilename(
            title="Select Font File",
            filetypes=[("Font Files", "*.ttf *.otf *.ttc"), ("All Files", "*.*")]
        )
        if filepath:
            self.font_path.set(filepath)
            self.log_status(f"Font path set to: {filepath}")

    def browse_balcon_path(self):
        filepath = filedialog.askopenfilename(
            title="Select balcon.exe",
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if filepath:
            self.balcon_path.set(filepath)
            self.log_status(f"Balcon path set to: {filepath}")
            self.update_voices_list() # Refresh voices after changing path


    def _update_color_preview(self, label_widget, hex_color):
         """Updates the background color of a label widget."""
         try:
             label_widget.config(background=hex_color)
         except tk.TclError: # Handle invalid color string if it somehow occurs
             label_widget.config(background="SystemButtonFace") # Default color


    def choose_text_color(self):
        color_code = colorchooser.askcolor(title="Choose Text Color", initialcolor=self.text_color_hex)
        if color_code and color_code[0] and color_code[1]: # Check if a color was selected
             self.text_color_rgb = tuple(int(c) for c in color_code[0])
             self.text_color_hex = color_code[1]
             self._update_color_preview(self.text_color_preview, self.text_color_hex)
             self.log_status(f"Text color set to: {self.text_color_rgb}")

    def choose_bg_color(self):
        color_code = colorchooser.askcolor(title="Choose Background Color", initialcolor=self.bg_color_hex)
        if color_code and color_code[0] and color_code[1]:
            self.bg_color_rgb = tuple(int(c) for c in color_code[0])
            self.bg_color_hex = color_code[1]
            self._update_color_preview(self.bg_color_preview, self.bg_color_hex)
            self.log_status(f"Background color set to: {self.bg_color_rgb}")

    def update_voices_list(self):
        """Gets voices from Balcon and updates the dropdown."""
        balcon = self.balcon_path.get()
        if not balcon or not os.path.exists(balcon):
            self.log_status("Cannot refresh voices: Balcon path is invalid or not set.")
            self.voice_combo['values'] = []
            self.selected_voice.set("")
            return

        self.log_status("Refreshing Balcon voices...")
        try:
            # Run in a separate thread to avoid blocking GUI if balcon is slow
            thread = threading.Thread(target=self._fetch_voices_thread, args=(balcon,), daemon=True)
            thread.start()
        except Exception as e:
             self.log_status(f"Error starting voice refresh thread: {e}")


    def _fetch_voices_thread(self, balcon_path):
        """Worker thread function to fetch voices."""
        voices = list_balcon_voices(balcon_path)
        # Use schedule method to update GUI from thread safely
        self.master.after(0, self._update_voice_combo_gui, voices)


    def _update_voice_combo_gui(self, voices):
        """Updates the voice combobox (must be called from main GUI thread)."""
        if voices:
            self.balcon_voices = voices
            self.voice_combo['values'] = self.balcon_voices
            if self.balcon_voices:
                current_selection = self.selected_voice.get()
                # Try to keep current selection if it's still valid, else set to first
                if current_selection not in self.balcon_voices:
                    self.selected_voice.set(self.balcon_voices[0])
            else:
                 self.selected_voice.set("") # No voices available
            self.log_status(f"Found {len(self.balcon_voices)} voices.")
        else:
            self.log_status("No voices found or error listing voices. Check Balcon path and installation.")
            self.voice_combo['values'] = []
            self.selected_voice.set("")


    def log_status(self, message):
        """Appends a message to the status text area."""
        self.status_area.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.status_area.insert(tk.END, f"[{timestamp}] {message}\n")
        self.status_area.see(tk.END) # Scroll to the bottom
        self.status_area.config(state=tk.DISABLED)
        self.master.update_idletasks() # Ensure GUI updates


    def start_generation(self):
        """Validates inputs and starts the video generation in a thread."""
        if self.is_generating:
            messagebox.showwarning("Busy", "Video generation is already in progress.")
            return

        # --- Input Validation ---
        text = self.text_input_area.get("1.0", tk.END).strip()
        if not text:
            messagebox.showerror("Input Error", "Please enter text or load from a file.")
            return

        output = self.output_path.get()
        if not output:
            messagebox.showerror("Input Error", "Please specify an output video file path.")
            return
        output_dir = os.path.dirname(output)
        if output_dir and not os.path.exists(output_dir):
             try:
                 os.makedirs(output_dir)
                 self.log_status(f"Created output directory: {output_dir}")
             except OSError as e:
                 messagebox.showerror("Output Error", f"Could not create output directory:\n{output_dir}\n{e}")
                 return

        balcon = self.balcon_path.get()
        if not balcon or not os.path.exists(balcon):
            messagebox.showerror("Input Error", f"Balcon path is invalid:\n{balcon}")
            return

        font = self.font_path.get()
        # Font path is optional, TextToVideo class handles default finding,
        # but we can check existence if a path *is* provided.
        if font and not os.path.exists(font):
             # Warn but allow proceeding, the class will try defaults if it fails
             messagebox.showwarning("Input Warning", f"Specified font file not found:\n{font}\nWill attempt default fonts.")
             # self.font_path.set("") # Optionally clear the invalid path
             # font = ""


        # --- Prepare Parameters ---
        params = {
            "font_path": font or None, # Pass None if empty string
            "font_size": self.font_size.get(),
            "fps": self.fps.get(),
            "duration_per_sentence": self.fixed_duration.get() if self.use_fixed_duration.get() else None,
            "transition_duration": self.transition_duration.get(),
            "width": self.width.get(),
            "height": self.height.get(),
            "background_color": self.bg_color_rgb,
            "text_color": self.text_color_rgb,
            "tts_engine": self.tts_engine.get(),
            "language": 'en', # Currently unused by balcon logic, keep default
            "voice": self.selected_voice.get() or None, # Pass None if empty
            "speed": self.speed.get(),
            "balcon_path": balcon,
            "status_callback": self.log_status # Pass the logging function
        }

        # --- Start Thread ---
        self.is_generating = True
        self.generate_button.config(text="Generating...", state=tk.DISABLED)
        self.log_status("Starting video generation...")

        thread = threading.Thread(target=self._generation_worker, args=(text, output, params), daemon=True)
        thread.start()


    def _generation_worker(self, text_content, output_file, params):
        """The actual work done in the background thread."""
        try:
            # Instantiate converter inside the thread
            converter = TextToVideo(**params)

            sentences = converter.split_into_sentences(text_content)
            if not sentences:
                 # Use master.after to show messagebox from main thread
                 self.master.after(0, lambda: messagebox.showerror("Input Error", "No valid sentences found in the input text."))
                 raise ValueError("No sentences found") # Stop thread execution

            self.log_status(f"Found {len(sentences)} sentences. Starting main process...")

            # Run the main generation function
            converter.generate_video(sentences, output_file)

            # If successful, notify user (via main thread)
            self.master.after(0, lambda: messagebox.showinfo("Success", f"Video generation complete!\nOutput saved to:\n{output_file}"))

        except Exception as e:
            # Log the full error from the thread
            self.log_status(f"GENERATION FAILED: {e}")
            # Show a simpler error message to the user (via main thread)
            self.master.after(0, lambda e=e: messagebox.showerror("Error", f"Video generation failed:\n{e}"))
            # No cleanup() call here, it should happen in TextToVideo's finally block

        finally:
            # Reset button state (via main thread) regardless of success/failure
            self.master.after(0, self._finalize_generation)


    def _finalize_generation(self):
        """Called from main thread to reset GUI after generation finishes or fails."""
        self.is_generating = False
        self.generate_button.config(text="Generate Video", state=tk.NORMAL)
        self.log_status("Generation process finished.")


# --- Main execution ---
if __name__ == "__main__":
    root = tk.Tk()
    # Set a default font for the GUI itself (optional)
    # default_font = tkfont.nametofont("TkDefaultFont")
    # default_font.configure(size=10)
    # root.option_add("*Font", default_font)

    app = TextToVideoApp(root)
    root.mainloop()
