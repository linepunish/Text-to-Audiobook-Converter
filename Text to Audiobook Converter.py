# --- 1. Dependency Check and Installation ---
import sys
import os
import subprocess
import importlib.util
import platform
import shutil # For checking ffmpeg

# --- Auto-relaunch with pythonw on Windows if necessary ---
# This must be done *before* significant GUI elements or console prints
# that you want to hide start, but after basic imports.
if platform.system() == "Windows":
    # Check if the current executable is python.exe (case-insensitive)
    current_executable = sys.executable.lower()
    if current_executable.endswith("python.exe"):
        # Construct the path to pythonw.exe
        pythonw_executable = current_executable.replace("python.exe", "pythonw.exe")

        # Check if pythonw.exe actually exists
        if os.path.exists(pythonw_executable):
            # Use sys.argv to pass any command-line arguments to the new process
            cmd = [pythonw_executable] + sys.argv

            # Relaunch the script using pythonw
            # We use Popen and detach so the current console process can exit immediately
            try:
                # Using DETACHED_PROCESS ensures the new process is independent
                DETACHED_PROCESS = 0x00000008
                subprocess.Popen(cmd, creationflags=DETACHED_PROCESS)
                # Exit the current python.exe process
                sys.exit(0)
            except Exception as e:
                # If relaunch fails, print error and continue with the console
                print(f"Error during pythonw relaunch: {e}", file=sys.stderr)
                print("Continuing with console visible.", file=sys.stderr)
        else:
            # If pythonw.exe is not found, print a warning and continue with the console
            print(f"Warning: pythonw.exe not found at {pythonw_executable}.", file=sys.stderr)
            print("Cannot auto-hide console. Continuing with console visible.", file=sys.stderr)
# --- End of auto-relaunch logic ---


# Define packages: {import_name: package_name_for_pip}
required_packages = {
    'numpy': 'numpy',
    'PIL': 'Pillow',       # Import name is PIL, package name is Pillow
    'cv2': 'opencv-python',
    'pydub': 'pydub',
    'tqdm': 'tqdm'
    # tkinter is assumed built-in
}

def check_and_install_packages(packages):
    """Checks for required packages and attempts to install missing ones using pip."""
    # This will print to the console if running with python.exe initially
    # If relaunched with pythonw, this output won't be seen unless captured
    # For dependency checks, seeing output is often desired.
    print("Checking required Python packages...")
    all_found = True
    packages_to_install = {}

    # ... (rest of your check_and_install_packages function) ...
    for import_name, package_name in packages.items():
        try:
            spec = importlib.util.find_spec(import_name)
            if spec is None:
                print(f"  - Package '{package_name}' (for import '{import_name}') not found.")
                packages_to_install[import_name] = package_name
                all_found = False
        except ModuleNotFoundError:
            print(f"  - Package '{package_name}' (for import '{import_name}') not found.")
            packages_to_install[import_name] = package_name
            all_found = False

    if not packages_to_install:
        print("All required Python packages are installed.")
        return True

    print("\nAttempting to install missing packages using pip...")
    print("NOTE: This requires an internet connection and may need administrator privileges.")
    install_success = True

    for import_name, package_name in packages_to_install.items():
        print(f"Installing {package_name}...")
        try:
            # Use sys.executable (which is pythonw if relaunched)
            # Allow the console for pip to show progress/errors during install if it pops up (less likely with pythonw but possible depending on system)
            # Or explicitly hide it: creation_flags = 0x08000000 if platform.system() == "Windows" else 0
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", package_name],
                check=True,
                capture_output=True, # Capture output
                text=True,           # Decode output as text
                # Add creationflags here if you want to hide the pip install window too,
                # but it's usually helpful to see it. Let's keep it visible for pip.
            )
            print(f"Successfully installed {package_name}.")
            # print(result.stdout) # Optional: show pip output
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to install {package_name}.", file=sys.stderr)
            print(f"Pip Error Output:\n{e.stderr}", file=sys.stderr)
            install_success = False
        except Exception as e:
            print(f"ERROR: An unexpected error occurred during installation of {package_name}: {e}", file=sys.stderr)
            install_success = False

    if not install_success:
        print("\nOne or more packages failed to install. Please install them manually:", file=sys.stderr)
        for _, pkg_name in packages_to_install.items():
             print(f"  pip install {pkg_name}", file=sys.stderr)
        return False

    print("Dependency installation attempt finished.")
    # Verify installation again after attempting install
    print("Verifying installation...")
    final_check_ok = True
    for import_name, package_name in packages_to_install.items():
          spec = importlib.util.find_spec(import_name)
          if spec is None:
              print(f"ERROR: Package '{package_name}' still not found after installation attempt.", file=sys.stderr)
              final_check_ok = False
    if final_check_ok and not all_found:
          print("Successfully installed and verified missing packages.")
    elif not final_check_ok:
          print("Verification failed for one or more packages.", file=sys.stderr)
          return False

    return True


# Check if FFMPEG exists in PATH (cannot install via pip)
def check_ffmpeg():
    print("Checking for ffmpeg executable...")
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        print(f"  - ffmpeg found at: {ffmpeg_path}")
        return True
    else:
        print("-------------------------------------------------------", file=sys.stderr)
        print("ERROR: ffmpeg executable not found in system PATH.", file=sys.stderr)
        print("Please install ffmpeg and ensure it's added to your", file=sys.stderr)
        print("system's environment variables (PATH).", file=sys.stderr)
        print("Download from: https://ffmpeg.org/download.html", file=sys.stderr)
        print("-------------------------------------------------------", file=sys.stderr)
        return False

# Run the checks
packages_ok = check_and_install_packages(required_packages)
ffmpeg_ok = check_ffmpeg()

# Decide if to continue - Let's allow continuing but the app will fail later if needed components missing
# if not packages_ok or not ffmpeg_ok:
#   print("\nExiting due to missing dependencies.", file=sys.stderr)
#   sys.exit(1)

# Removed the print("Dependency checks complete. Starting GUI...\n") and time.sleep(2) from here
# They were moved before the auto-relaunch logic if you want them to show only on initial launch


# --- 2. Original Imports (now potentially installed) ---
import re
import argparse
import tempfile
# shutil already imported
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageTk
import cv2
from tqdm import tqdm # tqdm progress won't show well in GUI, replaced with status updates
from pydub import AudioSegment
# import pydub.playback # Playback not needed for GUI generation
from pydub.silence import detect_leading_silence
import math
# Subprocess already imported
# Sys already imported
# OS already imported
# Platform already imported


# GUI specific imports
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, font as tkfont
import threading
import queue # For thread communication (optional for advanced progress)


# --- 3. Paste your TextToVideo class here ---
# ---    (Ensure subprocess calls are modified as shown below) ---
class TextToVideo:
    def __init__(self, font_path=None, font_size=40, fps=24, duration_per_sentence=None,
                 transition_duration=0.5, width=1280, height=720,
                 background_color=(0, 0, 0), text_color=(255, 255, 255),
                 tts_engine='balcon', language='en', voice=None, speed=0,
                 balcon_path='balcon.exe', status_callback=None):
        self.fps = fps
        self.duration_per_sentence = duration_per_sentence
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
        self.status_callback = status_callback

        # Font finding logic (remains the same)
        if font_path and os.path.exists(font_path):
            self.font_path = font_path
        else:
             if os.name == 'nt':  # Windows
                 font_options = [
                     "C:\\Windows\\Fonts\\arial.ttf", "C:\\Windows\\Fonts\\calibri.ttf", "C:\\Windows\\Fonts\\segoeui.ttf"
                 ]
             elif os.name == 'posix':  # macOS or Linux
                 font_options = [
                     "/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SF-Pro-Text-Regular.otf",
                     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/TTF/Arial.ttf"
                 ]
             else: font_options = []
             found_font = None
             for font in font_options:
                 if os.path.exists(font): found_font = font; break
             if found_font: self.font_path = found_font
             elif font_path: self.font_path = font_path
             else: self.font_path = None


        self.font_size = font_size
        self.pil_font = None # Delay loading

    def _load_font(self):
        # ... (remains the same) ...
        if self.pil_font is None:
            if not self.font_path or not os.path.exists(self.font_path):
                 raise FileNotFoundError(f"Font file not found or not specified: {self.font_path}")
            try:
                self.pil_font = ImageFont.truetype(self.font_path, self.font_size)
            except IOError as e:
                raise IOError(f"Error loading font '{self.font_path}': {e}")


    def _log_status(self, message):
        # ... (remains the same) ...
        if self.status_callback: self.status_callback(message)

    def split_into_sentences(self, text):
        # ... (remains the same) ...
        sentences = re.split(r'(?<=[.!?])\s+', text)
        return [s.strip() for s in sentences if s.strip()]

    # --- Centralized Subprocess Runner ---
    def _run_subprocess(self, cmd_list, process_name="command"):
        """Runs a subprocess, hiding console on Windows."""
        self._log_status(f"Running external {process_name}: {' '.join(cmd_list)}")
        creation_flags = 0
        if platform.system() == "Windows":
            # CREATE_NO_WINDOW = 0x08000000 # Hex constant for hiding console
            creation_flags = 0x08000000

        try:
            result = subprocess.run(
                cmd_list,
                check=True,          # Raise error if command fails
                capture_output=True, # Capture stdout/stderr
                text=True,           # Decode as text
                encoding='utf-8',    # Specify encoding
                errors='ignore',     # Ignore decoding errors if they occur
                creationflags=creation_flags # Hide console on Windows
            )
            # Optional: Log output if needed for debugging, but keep it minimal for status logs
            # if result.stdout: self._log_status(f"{process_name} stdout: {result.stdout[:200]}...")
            # if result.stderr: self._log_status(f"{process_name} stderr: {result.stderr[:200]}...")
            return result
        except FileNotFoundError as e:
            self._log_status(f"ERROR: {process_name} command not found: '{cmd_list[0]}'. Ensure it's installed and in the system PATH.")
            raise RuntimeError(f"Required command '{cmd_list[0]}' not found.") from e
        except subprocess.CalledProcessError as e:
            stdout = e.stdout if e.stdout else ""
            stderr = e.stderr if e.stderr else ""
            self._log_status(f"ERROR: {process_name} command failed (Return Code: {e.returncode}).")
            self._log_status(f"Command: {' '.join(cmd_list)}")
            if stdout: self._log_status(f"Stdout:\n{stdout}")
            if stderr: self._log_status(f"Stderr:\n{stderr}")
            raise RuntimeError(f"{process_name} command '{cmd_list[0]}' failed.") from e
        except Exception as e:
            self._log_status(f"ERROR: An unexpected error occurred running {process_name} command {' '.join(cmd_list)}: {e}")
            import traceback
            self._log_status(traceback.format_exc())
            raise # Re-raise the unexpected error

    # --- Modified methods using _run_subprocess ---

    def generate_speech_balcon(self, sentences):
        if not os.path.exists(self.balcon_path):
             raise FileNotFoundError(f"Balabolka command line tool not found at: {self.balcon_path}")

        self.temp_dir = tempfile.mkdtemp()
        audio_files = []
        durations = []

        self._log_status(f"Generating speech for {len(sentences)} sentences using Balabolka...")
        for i, sentence in enumerate(sentences):
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
                cmd.extend(['--encoding', 'utf8'])

                # Use the helper method to run Balcon (it handles hiding the console)
                self._run_subprocess(cmd, process_name="Balcon")

            except Exception as e:
                self._log_status(f"Error during speech generation setup for sentence {i+1}: {e}")
                if os.path.exists(text_file): os.remove(text_file)
                raise
            finally:
                if os.path.exists(text_file):
                    os.remove(text_file)

            if not os.path.exists(output_file) or os.path.getsize(output_file) == 0:
                 raise FileNotFoundError(f"Balcon ran successfully but failed to create a valid audio file: {output_file}")

            # Load audio and calculate duration (keep original logic)
            try:
                 audio = AudioSegment.from_wav(output_file)
                 duration_sec = len(audio) / 1000.0
                 durations.append(duration_sec + 0.05) # Add small buffer
                 audio_files.append(output_file)
            except Exception as e:
                 self._log_status(f"Error loading generated wav file {output_file}: {e}")
                 raise RuntimeError(f"Could not process generated audio for sentence {i+1}.") from e

        self._log_status("Speech generation complete.")
        return audio_files, durations


    def combine_audio_video(self, final_output_path, audio_path, temp_video_path):
        self._log_status("Combining video and audio using ffmpeg...")

        # Basic check if ffmpeg is available was done at startup, rely on _run_subprocess for execution errors.
        cmd = [
            'ffmpeg',
            '-i', temp_video_path,
            '-i', audio_path,
            '-map', '0:v:0',
            '-map', '1:a:0',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            '-y',
            final_output_path
        ]

        try:
            # Use the helper method to run ffmpeg (it handles hiding the console)
            self._run_subprocess(cmd, process_name="FFmpeg")
            self._log_status(f"Video with audio saved successfully as {final_output_path}")
        except Exception as e:
             self._log_status(f"Failed to combine video and audio. Check logs above.")
             raise RuntimeError(f"FFmpeg failed. See status log for details.") from e


    # --- Other TextToVideo methods (create_frame, _wrap_text, etc.) remain unchanged ---
    def generate_video(self, sentences, output_path):
        video = None
        temp_video_path = None # Initialize here
        try:
             # 1. Generate Speech (calls modified method)
             if self.tts_engine == 'balcon':
                 audio_files, speech_durations = self.generate_speech_balcon(sentences)
             else:
                 raise ValueError(f"Unsupported TTS engine: {self.tts_engine}")

             # 2. Calculate Timings
             self._log_status("Calculating display timings...")
             display_timings = []
             total_frames = 0
             for i, duration_sec in enumerate(speech_durations):
                 # Calculate display duration based on speech or fixed duration
                 display_duration = self.fixed_duration.get() if self.use_fixed_duration.get() else duration_sec
                 # Ensure a minimum duration for short sentences or silences
                 display_duration = max(display_duration, self.transition_duration * 2 + 0.1) # Min duration covers transitions + buffer

                 start_time = total_frames / self.fps
                 end_time = start_time + display_duration
                 display_timings.append((start_time, end_time))
                 total_frames = int(end_time * self.fps) # Update total frames based on end time

             self._log_status(f"Total video duration calculated: {total_frames / self.fps:.2f} seconds")

             # 3. Prepare Video Writer
             temp_video_path = os.path.join(self.temp_dir, "temp_video.avi") # Use a temp path
             fourcc = cv2.VideoWriter_fourcc(*'DIVX') # Use a common codec like DIVX or XVID for AVI
             video = cv2.VideoWriter(temp_video_path, fourcc, self.fps, (self.width, self.height))
             if not video.isOpened():
                 raise IOError(f"Could not open video writer for path: {temp_video_path}")
             self._log_status(f"Video writer initialized for {temp_video_path}")

             # 4. Generate Frames
             self._log_status("Generating video frames...")
             frame_count = 0
             for i, sentence in enumerate(sentences):
                 start_time, end_time = display_timings[i]
                 num_frames_in_segment = int((end_time - start_time) * self.fps)
                 frames_per_transition = int(self.transition_duration * self.fps)
                 frames_per_stable = num_frames_in_segment - 2 * frames_per_transition

                 if frames_per_stable < 0:
                     # Adjust if duration was too short for full transitions
                     frames_per_stable = 0
                     frames_per_transition = num_frames_in_segment // 2 # Use half the frames for each transition

                 # Fade In
                 for j in range(frames_per_transition):
                     fade = j / frames_per_transition
                     frame = self.create_frame(sentence, fade=fade)
                     video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                     frame_count += 1

                 # Stable Display
                 stable_start_frame = frame_count
                 stable_end_frame = stable_start_frame + frames_per_stable
                 while frame_count < stable_end_frame:
                     frame = self.create_frame(sentence, fade=1.0)
                     video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                     frame_count += 1

                 # Fade Out
                 for j in range(frames_per_transition):
                     fade = 1.0 - (j / frames_per_transition)
                     frame = self.create_frame(sentence, fade=fade)
                     video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                     frame_count += 1

             # Ensure total frames match calculation if slight rounding differences occurred
             while frame_count < total_frames:
                  # Add final black frame or repeat last frame if needed
                  frame = self.create_frame("", fade=0.0) # Add a black frame
                  video.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                  frame_count += 1

             self._log_status("Frame generation complete.")

             # 5. Create Synchronized Audio (remains the same)
             synchronized_audio_path = self.create_synchronized_audio(audio_files, display_timings)

             # 6. Combine Audio and Video (calls modified method)
             self.combine_audio_video(output_path, synchronized_audio_path, temp_video_path)

             self._log_status("Video generation process completed successfully!")

        except Exception as e:
            self._log_status(f"ERROR during video generation: {e}")
            import traceback
            self._log_status(f"Traceback:\n{traceback.format_exc()}")
            raise
        finally:
            if video is not None and video.isOpened():
                 self._log_status("Releasing video writer...")
                 video.release()
            # Cleanup temp video file if it exists and wasn't needed or combining failed
            if temp_video_path and os.path.exists(temp_video_path):
                try: os.remove(temp_video_path)
                except Exception as e: self._log_status(f"Warning: Failed to remove temporary video file {temp_video_path}: {e}")
            self.cleanup() # Ensure cleanup happens for the temp dir

    def create_frame(self, text, fade=1.0):
        # --- PASTE create_frame method here ---
        self._load_font() # Ensure font is loaded before drawing
        img = Image.new('RGB', (self.width, self.height), self.background_color)
        draw = ImageDraw.Draw(img)
        current_font = self.pil_font
        temp_font_size = self.font_size
        # Font scaling loop if text doesn't fit
        while temp_font_size > 5:
            try:
                current_font = ImageFont.truetype(self.font_path, temp_font_size)
                lines = self._wrap_text(text, current_font)
                total_height = self._calculate_text_block_height(lines, current_font)
                if total_height <= self.height - 40: # Add some margin
                    break
                else:
                    temp_font_size = int(temp_font_size * 0.9)
                    # Optional: log font size reduction, but might be noisy
                    # self._log_status(f"Text too long, reducing font size to {temp_font_size}...")
            except IOError:
                self._log_status(f"Warning: Could not load font at size {temp_font_size}. Using previous size.")
                break # Stop trying to resize if font loading fails
        text_color = tuple(int(c * fade) for c in self.text_color)
        self._draw_wrapped_text(draw, lines, text_color, current_font)
        return np.array(img)

    def _wrap_text(self, text, font):
        # --- PASTE _wrap_text method here ---
        words = text.split(); lines = []; current_line = []; max_width = self.width - 100 # Add horizontal margin
        for word in words:
            test_line_list = current_line + [word]; test_line = ' '.join(test_line_list)
            try: left, top, right, bottom = font.getbbox(test_line); width = right - left
            except AttributeError: width, _ = font.getsize(test_line) # Fallback for older Pillow versions
            if width <= max_width: current_line.append(word)
            else:
                if not current_line: # Handle case where a single word is wider than max_width
                     lines.append(word)
                else:
                    lines.append(' '.join(current_line)); current_line = [word]
        if current_line: lines.append(' '.join(current_line))
        return lines

    def _calculate_text_block_height(self, lines, font):
          # --- PASTE _calculate_text_block_height method here ---
        if not lines: return 0
        try: _, top, _, bottom = font.getbbox('A'); line_h = bottom - top
        except AttributeError: _, line_h = font.getsize('A') # Fallback for older Pillow versions
        line_spacing_multiplier = 1.4 # Adjust line spacing as needed
        total_height = line_h * len(lines) * line_spacing_multiplier
        return total_height

    def _draw_wrapped_text(self, draw, lines, text_color, font):
        # --- PASTE _draw_wrapped_text method here ---
        if not lines: return
        try: _, top, _, bottom = font.getbbox('A'); line_h = bottom - top
        except AttributeError: _, line_h = font.getsize('A') # Fallback for older Pillow versions
        line_spacing_multiplier = 1.4; line_height_pixels = line_h * line_spacing_multiplier
        total_height = line_height_pixels * len(lines); y = (self.height - total_height) // 2 # Vertically center the text block
        for line in lines:
             try: left, _, right, _ = font.getbbox(line); width = right - left
             except AttributeError: width, _ = font.getsize(line) # Fallback for older Pillow versions
             x = (self.width - width) // 2; # Horizontally center each line
             draw.text((x, y), line, font=font, fill=text_color)
             y += line_height_pixels

    def create_silent_audio_segment(self, duration_ms):
        # --- PASTE create_silent_audio_segment method here ---
        return AudioSegment.silent(duration=duration_ms)

    def create_synchronized_audio(self, audio_files, display_timings):
        # --- PASTE create_synchronized_audio method here ---
        self._log_status("Creating synchronized audio track...")
        combined_audio = AudioSegment.empty(); current_position_ms = 0
        for i, (audio_file, (start_time, end_time)) in enumerate(zip(audio_files, display_timings)):
            start_ms = int(start_time * 1000); end_ms = int(end_time * 1000); display_duration_ms = end_ms - start_ms
            try:
                speech = AudioSegment.from_file(audio_file); speech_duration_ms = len(speech)
                # Add silence before the speech if needed to match display timing
                if start_ms > current_position_ms:
                    silence_duration = start_ms - current_position_ms;
                    silence = self.create_silent_audio_segment(silence_duration)
                    combined_audio += silence;
                    current_position_ms = start_ms

                # The speech should fit within the 'stable' part of the display duration (total - 2*transition)
                target_speech_duration_ms = display_duration_ms - int(self.transition_duration * 2 * 1000)

                if target_speech_duration_ms <= 0:
                    self._log_status(f"Warning: Display duration too short for transitions for sentence {i+1}. Using minimum 10ms for speech.")
                    target_speech_duration_ms = 10 # Minimum speech duration

                # Adjust speech speed if necessary
                if speech_duration_ms > target_speech_duration_ms:
                    speed_factor = speech_duration_ms / target_speech_duration_ms;
                    # self._log_status(f"  Adjusting speed for sentence {i+1} (Factor: {speed_factor:.2f})") # Optional: log speed adjustment
                    try:
                         # New pydub speedup method
                         speech = speech.speedup(playback_speed=speed_factor)
                         # Ensure consistent frame rate after speedup
                         speech = speech.set_frame_rate(44100)
                    except AttributeError:
                         # Older pydub speed adjustment method (less accurate)
                         # self._log_status("  (Using older pydub speed adjustment method)")
                         new_frame_rate = int(speech.frame_rate * speed_factor);
                         speech = speech._spawn(speech.raw_data, overrides={"frame_rate": new_frame_rate});
                         speech = speech.set_frame_rate(44100) # Reset to a standard rate

                elif speech_duration_ms < target_speech_duration_ms:
                    # Add padding if speech is shorter than target
                    padding_needed = target_speech_duration_ms - speech_duration_ms;
                    speech += self.create_silent_audio_segment(padding_needed)

                combined_audio += speech;
                current_position_ms += len(speech)

                # Add silence for the transition OUT duration
                transition_silence_ms = int(self.transition_duration * 1000);
                combined_audio += self.create_silent_audio_segment(transition_silence_ms);
                current_position_ms += transition_silence_ms # This accounts for the silence *after* the speech segment

            except Exception as e:
                self._log_status(f"Error processing audio for sentence {i+1} ({audio_file}): {e}")
                # If audio processing fails, add silence for the expected display duration
                display_duration_ms = int((end_time - start_time) * 1000)
                if display_duration_ms > 0:
                    combined_audio += self.create_silent_audio_segment(display_duration_ms);
                    current_position_ms += display_duration_ms
                # Decide if to re-raise or just log and continue with silence
                # For a GUI, maybe just log and continue to avoid crashing the app?
                # raise RuntimeError(f"Failed to process audio for sentence {i+1}.") from e # Re-raise if critical

        combined_audio_path = os.path.join(self.temp_dir, "synchronized_audio.wav")
        try:
            combined_audio.export(combined_audio_path, format="wav");
            self._log_status("Synchronized audio track created.")
        except Exception as e:
            self._log_status(f"Error exporting combined audio: {e}");
            raise RuntimeError("Failed to export combined audio.") from e
        return combined_audio_path


    def cleanup(self):
        # --- PASTE cleanup method here ---
        if self.temp_dir and os.path.exists(self.temp_dir):
            self._log_status(f"Cleaning up temporary directory: {self.temp_dir}")
            try:
                # Use onerror handler for robust cleanup
                def onerror(func, path, exc_info):
                    import warnings
                    warnings.warn(f"Could not remove {path}: {exc_info[1]}")
                shutil.rmtree(self.temp_dir, onerror=onerror)
                self.temp_dir = None # Reset temp_dir after attempt
                self._log_status("Cleanup complete.")
            except Exception as e:
                # This outer catch might be redundant with onerror but kept for safety
                self._log_status(f"Warning: Failed to completely remove temporary directory {self.temp_dir}: {e}")

# --- End of TextToVideo class ---


# --- 4. list_balcon_voices function (Modified subprocess call) ---
def list_balcon_voices(balcon_path):
    if not os.path.exists(balcon_path):
        # Log this error in the GUI status if possible
        # For now, return a list indicating the error
        return ["ERROR: Balcon executable not found at specified path."]

    creation_flags = 0
    if platform.system() == "Windows":
        # CREATE_NO_WINDOW = 0x08000000
        creation_flags = 0x08000000

    try:
        # Use text=True and capture_output for cleaner handling
        result = subprocess.run(
            [balcon_path, '-l'],
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            creationflags=creation_flags # Hide console on Windows
        )
        voices = []
        # Assuming the output format is lines of voice names after some header
        # Adjust parsing based on actual 'balcon -l' output if needed
        for line in result.stdout.splitlines():
              line = line.strip()
              # Simple heuristic to skip header lines
              if line and not line.startswith("---") and not line.lower().startswith("available"):
                  voices.append(line)
        if not voices and result.stderr:
             # If no voices found but there was stderr output, maybe it's an error?
             # Append stderr to voices list for user info in GUI
             voices.append("Warning: No voices listed. Stderr:")
             voices.extend(result.stderr.splitlines())
        elif not voices:
             # If no voices and no stderr, maybe just no voices are installed?
             voices = ["No voices found."]

        return voices

    except FileNotFoundError:
        # This is handled by the initial os.path.exists check now, but keeping for robustness
        return ["ERROR: Balcon executable not found."]
    except subprocess.CalledProcessError as e:
         # Log error via GUI status if possible
         # Return error message in list for GUI display
         error_msg = f"ERROR: Balcon failed (Return Code: {e.returncode})"
         if e.stderr:
             error_msg += f"\nStderr: {e.stderr.strip()[:200]}..."
         return [error_msg]
    except Exception as e:
         # Log error via GUI status if possible
         # Return error message in list for GUI display
         return [f"ERROR: Unexpected error listing voices: {e}"]


# --- 5. TextToVideoApp Class (Modified voice update logic) ---
class TextToVideoApp:
    # --- Paste the __init__ method and other GUI methods here ---
    # --- Modify _update_voice_combo_gui to handle error messages ---
    def __init__(self, master):
        # --- PASTE __init__ method here ---
        self.master = master; master.title("Text to Video Converter"); master.geometry("800x750")
        self.style = ttk.Style(); self.style.theme_use('clam')

        self.input_text = tk.StringVar();
        self.output_path = tk.StringVar(value="output.mp4");
        self.font_path = tk.StringVar()

        self.font_size = tk.IntVar(value=40);
        self.fps = tk.IntVar(value=24);
        self.use_fixed_duration = tk.BooleanVar(value=False)
        self.fixed_duration = tk.DoubleVar(value=5.0);
        self.transition_duration = tk.DoubleVar(value=0.5);
        self.width = tk.IntVar(value=1280);
        self.height = tk.IntVar(value=720);

        self.bg_color_rgb = (0, 0, 0); self.bg_color_hex = "#000000";
        self.text_color_rgb = (255, 255, 255); self.text_color_hex = "#ffffff";

        self.tts_engine = tk.StringVar(value="balcon");
        self.balcon_path = tk.StringVar(value=self._find_default_balcon());
        self.balcon_voices = [];
        self.selected_voice = tk.StringVar();
        self.speed = tk.IntVar(value=0);
        self.is_generating = False

        main_frame = ttk.Frame(master, padding="10"); main_frame.pack(fill=tk.BOTH, expand=True);
        main_frame.columnconfigure(1, weight=1)

        # Input Text Area
        row_idx = 0;
        ttk.Label(main_frame, text="Input Text:").grid(row=row_idx, column=0, sticky="nw", pady=2)
        self.text_input_area = tk.Text(main_frame, height=10, width=60, wrap=tk.WORD, relief=tk.SOLID, borderwidth=1);
        self.text_input_area.grid(row=row_idx, column=1, columnspan=2, sticky="ew", pady=2)
        text_scrollbar = ttk.Scrollbar(main_frame, orient=tk.VERTICAL, command=self.text_input_area.yview);
        text_scrollbar.grid(row=row_idx, column=3, sticky="ns")
        self.text_input_area['yscrollcommand'] = text_scrollbar.set;
        row_idx += 1

        # Load Text Button
        load_button = ttk.Button(main_frame, text="Load Text from File...", command=self.load_text_file);
        load_button.grid(row=row_idx, column=1, columnspan=2, sticky="w", pady=5);
        row_idx += 1

        # Output File Selection
        ttk.Label(main_frame, text="Output Video File:").grid(row=row_idx, column=0, sticky="w", pady=2)
        output_entry = ttk.Entry(main_frame, textvariable=self.output_path, width=50);
        output_entry.grid(row=row_idx, column=1, sticky="ew", padx=(0, 5))
        output_button = ttk.Button(main_frame, text="Browse...", command=self.browse_output_file);
        output_button.grid(row=row_idx, column=2, sticky="w");
        row_idx += 1

        # Notebook for Settings Tabs
        notebook = ttk.Notebook(main_frame);
        notebook.grid(row=row_idx, column=0, columnspan=4, sticky="nsew", pady=10);
        main_frame.rowconfigure(row_idx, weight=1) # Make notebook expandable vertically

        video_frame = ttk.Frame(notebook, padding="10");
        audio_frame = ttk.Frame(notebook, padding="10");
        text_style_frame = ttk.Frame(notebook, padding="10")

        notebook.add(video_frame, text=' Video Settings ');
        notebook.add(text_style_frame, text=' Text & Style '); # Moved text style to its own tab
        notebook.add(audio_frame, text=' Audio (TTS) Settings ')

        # --- Video Settings Tab ---
        vf_row = 0;
        video_frame.columnconfigure(1, weight=1);
        video_frame.columnconfigure(3, weight=1) # Allow columns for spinboxes/entries to expand

        ttk.Label(video_frame, text="Width:").grid(row=vf_row, column=0, sticky="w", pady=3);
        ttk.Spinbox(video_frame, from_=100, to=7680, textvariable=self.width, width=8).grid(row=vf_row, column=1, sticky="w", pady=3)

        ttk.Label(video_frame, text="Height:").grid(row=vf_row, column=2, sticky="w", padx=(10,0), pady=3);
        ttk.Spinbox(video_frame, from_=100, to=4320, textvariable=self.height, width=8).grid(row=vf_row, column=3, sticky="w", pady=3);
        vf_row += 1

        ttk.Label(video_frame, text="FPS:").grid(row=vf_row, column=0, sticky="w", pady=3);
        ttk.Spinbox(video_frame, from_=1, to=120, textvariable=self.fps, width=8).grid(row=vf_row, column=1, sticky="w", pady=3)

        ttk.Label(video_frame, text="Transition (s):").grid(row=vf_row, column=2, sticky="w", padx=(10,0), pady=3);
        ttk.Spinbox(video_frame, from_=0.0, to=10.0, increment=0.1, format="%.1f", textvariable=self.transition_duration, width=8).grid(row=vf_row, column=3, sticky="w", pady=3);
        vf_row += 1

        self.fixed_dur_check = ttk.Checkbutton(video_frame, text="Fixed Duration/Sentence:", variable=self.use_fixed_duration, command=self.toggle_fixed_duration);
        self.fixed_dur_check.grid(row=vf_row, column=0, columnspan=2, sticky="w", pady=3)
        self.fixed_dur_spinbox = ttk.Spinbox(video_frame, from_=0.1, to=300.0, increment=0.1, format="%.1f", textvariable=self.fixed_duration, width=8, state=tk.DISABLED);
        self.fixed_dur_spinbox.grid(row=vf_row, column=2, columnspan=2, sticky="w", pady=3)
        vf_row += 1

        # --- Text & Style Tab ---
        tsf_row = 0;
        text_style_frame.columnconfigure(1, minsize=150); # Give font path entry some space
        text_style_frame.columnconfigure(3, weight=1) # Allow empty column to push button left

        ttk.Label(text_style_frame, text="Font File:").grid(row=tsf_row, column=0, sticky="w", pady=3);
        ttk.Entry(text_style_frame, textvariable=self.font_path, width=40).grid(row=tsf_row, column=1, sticky="ew", padx=(0, 5));
        ttk.Button(text_style_frame, text="Browse...", command=self.browse_font_file).grid(row=tsf_row, column=2, sticky="w");
        tsf_row += 1

        ttk.Label(text_style_frame, text="Font Size:").grid(row=tsf_row, column=0, sticky="w", pady=3);
        ttk.Spinbox(text_style_frame, from_=8, to=200, textvariable=self.font_size, width=8).grid(row=tsf_row, column=1, sticky="w", pady=3);
        tsf_row += 1

        ttk.Label(text_style_frame, text="Text Color:").grid(row=tsf_row, column=0, sticky="w", pady=3)
        self.text_color_button = tk.Button(text_style_frame, text="Choose...", command=self.choose_text_color, width=10, relief=tk.GROOVE);
        self.text_color_button.grid(row=tsf_row, column=1, sticky="w", pady=3)
        self.text_color_preview = tk.Label(text_style_frame, text="  ", background=self.text_color_hex, relief=tk.SUNKEN, borderwidth=1);
        self.text_color_preview.grid(row=tsf_row, column=2, sticky="w", padx=5);
        tsf_row += 1

        ttk.Label(text_style_frame, text="Background Color:").grid(row=tsf_row, column=0, sticky="w", pady=3)
        self.bg_color_button = tk.Button(text_style_frame, text="Choose...", command=self.choose_background_color, width=10, relief=tk.GROOVE);
        self.bg_color_button.grid(row=tsf_row, column=1, sticky="w", pady=3)
        self.bg_color_preview = tk.Label(text_style_frame, text="  ", background=self.bg_color_hex, relief=tk.SUNKEN, borderwidth=1);
        self.bg_color_preview.grid(row=tsf_row, column=2, sticky="w", padx=5);
        tsf_row += 1

        # --- Audio (TTS) Settings Tab ---
        af_row = 0;
        audio_frame.columnconfigure(1, weight=1)

        ttk.Label(audio_frame, text="TTS Engine:").grid(row=af_row, column=0, sticky="w", pady=3);
        self.tts_engine_combo = ttk.Combobox(audio_frame, textvariable=self.tts_engine, values=["balcon"], state="readonly");
        self.tts_engine_combo.grid(row=af_row, column=1, sticky="ew", pady=3);
        self.tts_engine_combo.bind('<<ComboboxSelected>>', self._on_tts_engine_changed)
        af_row += 1

        ttk.Label(audio_frame, text="Balabolka Path:").grid(row=af_row, column=0, sticky="w", pady=3);
        ttk.Entry(audio_frame, textvariable=self.balcon_path).grid(row=af_row, column=1, sticky="ew", padx=(0, 5));
        ttk.Button(audio_frame, text="Browse...", command=self.browse_balcon_path).grid(row=af_row, column=2, sticky="w");
        af_row += 1

        ttk.Label(audio_frame, text="Voice:").grid(row=af_row, column=0, sticky="w", pady=3);
        self.voice_combo = ttk.Combobox(audio_frame, textvariable=self.selected_voice, state="readonly");
        self.voice_combo.grid(row=af_row, column=1, sticky="ew", pady=3);
        ttk.Button(audio_frame, text="Refresh Voices", command=self.refresh_voices).grid(row=af_row, column=2, sticky="w")
        af_row += 1

        ttk.Label(audio_frame, text="Speed:").grid(row=af_row, column=0, sticky="w", pady=3);
        ttk.Spinbox(audio_frame, from_=-10, to=10, textvariable=self.speed, width=8).grid(row=af_row, column=1, sticky="w", pady=3);
        af_row += 1

        # Status Bar
        row_idx += 1 # New row after notebook
        self.status_label = ttk.Label(main_frame, text="Ready.", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.grid(row=row_idx, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        row_idx += 1

        # Generate Button
        generate_button = ttk.Button(main_frame, text="Generate Video", command=self.start_generation_thread)
        generate_button.grid(row=row_idx, column=0, columnspan=4, sticky="s", pady=10)


        # Initial state setup
        self._update_voice_combo_gui()
        self.toggle_fixed_duration() # Set initial state based on var

    # --- PASTE remaining methods of TextToVideoApp class here ---
    # (load_text_file, browse_output_file, browse_font_file, browse_balcon_path,
    #  choose_text_color, choose_background_color, _rgb_to_hex, _hex_to_rgb,
    #  toggle_fixed_duration, _find_default_balcon, refresh_voices,
    #  _update_voice_combo_gui, _on_tts_engine_changed, update_status,
    #  run_generation, start_generation_thread, check_generation_thread, on_generation_complete)


    def load_text_file(self):
        # --- PASTE load_text_file method here ---
        filepath = filedialog.askopenfilename(
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")]
        )
        if not filepath:
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                self.text_input_area.delete(1.0, tk.END)
                self.text_input_area.insert(tk.END, content)
        except Exception as e:
            messagebox.showerror("Error Loading File", f"Could not read file: {e}")

    def browse_output_file(self):
        # --- PASTE browse_output_file method here ---
        filepath = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")],
            initialfile="output.mp4"
        )
        if filepath:
            self.output_path.set(filepath)

    def browse_font_file(self):
        # --- PASTE browse_font_file method here ---
        filepath = filedialog.askopenfilename(
            filetypes=[("Font Files", "*.ttf *.otf *.ttc"), ("All Files", "*.*")]
        )
        if filepath:
            self.font_path.set(filepath)

    def browse_balcon_path(self):
        # --- PASTE browse_balcon_path method here ---
        filepath = filedialog.askopenfilename(
            filetypes=[("Executable Files", "*.exe"), ("All Files", "*.*")]
        )
        if filepath:
            self.balcon_path.set(filepath)
            self.refresh_voices() # Refresh voices when path changes

    def choose_text_color(self):
        # --- PASTE choose_text_color method here ---
        color_code = colorchooser.askcolor(title="Choose Text Color", initialcolor=self.text_color_hex)
        if color_code:
            rgb, hex_color = color_code
            if hex_color:
                self.text_color_rgb = tuple(int(c) for c in rgb)
                self.text_color_hex = hex_color
                self.text_color_preview.config(background=self.text_color_hex)

    def choose_background_color(self):
        # --- PASTE choose_background_color method here ---
        color_code = colorchooser.askcolor(title="Choose Background Color", initialcolor=self.bg_color_hex)
        if color_code:
            rgb, hex_color = color_code
            if hex_color:
                self.bg_color_rgb = tuple(int(c) for c in rgb)
                self.bg_color_hex = hex_color
                self.bg_color_preview.config(background=self.bg_color_hex)

    def _rgb_to_hex(self, rgb):
        # --- PASTE _rgb_to_hex method here ---
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'

    def _hex_to_rgb(self, hex_color):
        # --- PASTE _hex_to_rgb method here ---
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def toggle_fixed_duration(self):
        # --- PASTE toggle_fixed_duration method here ---
        if self.use_fixed_duration.get():
            self.fixed_dur_spinbox.config(state=tk.NORMAL)
        else:
            self.fixed_dur_spinbox.config(state=tk.DISABLED)

    def _find_default_balcon(self):
         # --- PASTE _find_default_balcon method here ---
         # Common installation path heuristic for Balabolka command line tool
         if platform.system() == "Windows":
             program_files = os.environ.get("ProgramFiles(x86)", os.environ.get("ProgramFiles", "C:\\Program Files"))
             balabolka_path = os.path.join(program_files, "Balabolka", "balcon.exe")
             if os.path.exists(balabolka_path):
                 return balabolka_path
         return "balcon.exe" # Return just the executable name if not found, relies on PATH

    def refresh_voices(self):
        # --- PASTE refresh_voices method here ---
        balcon_exe_path = self.balcon_path.get()
        if not balcon_exe_path:
            self.update_status("Balabolka path is not set.", is_error=True)
            self.balcon_voices = []
        elif not os.path.exists(balcon_exe_path):
             self.update_status(f"Balabolka executable not found at '{balcon_exe_path}'.", is_error=True)
             self.balcon_voices = ["ERROR: Balcon not found at path"]
        else:
             self.update_status("Refreshing Balabolka voices...")
             # list_balcon_voices now returns potential error strings in the list
             voices = list_balcon_voices(balcon_exe_path)
             if voices and voices[0].startswith("ERROR"):
                 self.update_status(voices[0], is_error=True)
                 self.balcon_voices = voices # Store error message in list
             else:
                 self.balcon_voices = voices
                 self.update_status(f"Found {len(self.balcon_voices)} Balabolka voices.")

        self._update_voice_combo_gui()


    def _update_voice_combo_gui(self):
        # --- PASTE _update_voice_combo_gui method here ---
        self.voice_combo['values'] = self.balcon_voices
        if self.balcon_voices and not self.balcon_voices[0].startswith("ERROR"):
            # Select the first voice if available and not an error message
            current_voice = self.selected_voice.get()
            if current_voice in self.balcon_voices:
                self.voice_combo.set(current_voice) # Keep current selection if still valid
            else:
                self.voice_combo.set(self.balcon_voices[0])
            self.voice_combo.config(state="readonly")
        else:
            # Disable combo box if no voices or an error occurred
            self.voice_combo.set(self.balcon_voices[0] if self.balcon_voices else "No voices found")
            self.voice_combo.config(state="disabled")


    def _on_tts_engine_changed(self, event=None):
        # --- PASTE _on_tts_engine_changed method here ---
        # Currently only 'balcon' is supported, but placeholder for future
        selected_engine = self.tts_engine.get()
        if selected_engine == 'balcon':
             self.balcon_path.set(self._find_default_balcon()) # Reset path helper
             self.refresh_voices() # Refresh voices for Balcon
        else:
             # Disable voice/path settings for other engines if they are added
             self.balcon_path.set("")
             self.balcon_voices = []
             self._update_voice_combo_gui()
             self.update_status(f"TTS Engine '{selected_engine}' not fully supported yet.", is_error=False)


    def update_status(self, message, is_error=False):
        # --- PASTE update_status method here ---
        color = "red" if is_error else "black"
        self.status_label.config(text=message, foreground=color)
        self.master.update_idletasks() # Update GUI immediately


    def run_generation(self):
        # --- PASTE run_generation method here ---
        try:
            self.update_status("Starting video generation...")
            input_text = self.text_input_area.get(1.0, tk.END).strip()
            if not input_text:
                self.update_status("Input text is empty.", is_error=True)
                messagebox.showwarning("Input Error", "Please enter text to convert to video.")
                return False

            output_file = self.output_path.get().strip()
            if not output_file:
                 self.update_status("Output file path is not set.", is_error=True)
                 messagebox.showwarning("Input Error", "Please specify an output file path.")
                 return False

            if not output_file.lower().endswith('.mp4'):
                output_file += '.mp4'
                self.output_path.set(output_file) # Update GUI with corrected path

            # Ensure parent directory exists
            output_dir = os.path.dirname(output_file)
            if output_dir and not os.path.exists(output_dir):
                try:
                    os.makedirs(output_dir)
                    self.update_status(f"Created output directory: {output_dir}")
                except Exception as e:
                    self.update_status(f"Error creating output directory {output_dir}: {e}", is_error=True)
                    messagebox.showerror("Directory Error", f"Could not create output directory:\n{output_dir}\n{e}")
                    return False

            tts_engine = self.tts_engine.get()
            if tts_engine == 'balcon':
                balcon_path = self.balcon_path.get().strip()
                if not balcon_path or not os.path.exists(balcon_path):
                    self.update_status(f"Balabolka path invalid or not set: '{balcon_path}'", is_error=True)
                    messagebox.showerror("Configuration Error", f"Balabolka executable not found at:\n{balcon_path}\nPlease set the correct path in Audio Settings.")
                    return False
                selected_voice = self.selected_voice.get()
                if not selected_voice or selected_voice.startswith("ERROR") or selected_voice == "No voices found":
                    self.update_status("Selected voice is invalid or none found.", is_error=True)
                    messagebox.showerror("Configuration Error", "Please select a valid voice or refresh voices.")
                    return False
            else:
                 self.update_status(f"Unsupported TTS engine: {tts_engine}", is_error=True)
                 messagebox.showerror("Configuration Error", f"Unsupported TTS engine: {tts_engine}")
                 return False

            font_path = self.font_path.get().strip()
            # Allow using default font if path is empty, but warn if explicit path is invalid
            if font_path and not os.path.exists(font_path):
                 self.update_status(f"Font file not found: '{font_path}'. Using default font.", is_error=False)
                 font_path = None # Use default font logic in TextToVideo init

            video_generator = TextToVideo(
                font_path=font_path,
                font_size=self.font_size.get(),
                fps=self.fps.get(),
                duration_per_sentence=self.fixed_duration.get() if self.use_fixed_duration.get() else None,
                transition_duration=self.transition_duration.get(),
                width=self.width.get(),
                height=self.height.get(),
                background_color=self.bg_color_rgb,
                text_color=self.text_color_rgb,
                tts_engine=tts_engine,
                voice=selected_voice,
                speed=self.speed.get(),
                balcon_path=balcon_path,
                status_callback=self.update_status # Pass the status update method
            )

            sentences = video_generator.split_into_sentences(input_text)
            if not sentences:
                self.update_status("No valid sentences found in the input text.", is_error=True)
                messagebox.showwarning("Input Error", "No valid sentences found after splitting the text.")
                return False


            video_generator.generate_video(sentences, output_file)
            self.update_status(f"Video successfully generated: {output_file}")
            return True

        except FileNotFoundError as e:
             # Catch specific file not found errors from within the generator
             self.update_status(f"File Not Found Error: {e}", is_error=True)
             messagebox.showerror("File Error", str(e))
             return False
        except RuntimeError as e:
             # Catch specific runtime errors (like subprocess failures)
             self.update_status(f"Runtime Error: {e}", is_error=True)
             messagebox.showerror("Generation Error", str(e))
             return False
        except Exception as e:
            # Catch any other unexpected errors
            import traceback
            print(f"An unexpected error occurred:\n{traceback.format_exc()}", file=sys.stderr) # Print traceback to console/log
            self.update_status(f"An unexpected error occurred: {type(e).__name__} - {e}", is_error=True)
            messagebox.showerror("Unexpected Error", f"An unexpected error occurred during generation:\n{e}")
            return False
        finally:
             # Cleanup happens inside TextToVideo.generate_video's finally block
             pass # No need for global cleanup here


    def start_generation_thread(self):
        # --- PASTE start_generation_thread method here ---
        if self.is_generating:
            messagebox.showinfo("Info", "Generation is already in progress.")
            return

        self.is_generating = True
        # Disable GUI elements during generation
        self.toggle_gui_state(False)
        self.update_status("Starting generation thread...")

        # Use a thread to run the potentially long process
        self.generation_thread = threading.Thread(target=self.run_generation_wrapper)
        self.generation_thread.start()

        # Start checking the thread status periodically
        self.master.after(100, self.check_generation_thread)

    def run_generation_wrapper(self):
        # Wrapper function to run in the thread and handle completion status
        success = self.run_generation() # This calls your main generation logic
        # Communicate completion back to the main GUI thread (optional if just setting flag)
        self.master.after(0, lambda: self.on_generation_complete(success))


    def check_generation_thread(self):
        # --- PASTE check_generation_thread method here ---
        if self.generation_thread.is_alive():
            # Thread is still running, schedule the check again
            self.master.after(100, self.check_generation_thread)
        # else:
            # Thread finished, on_generation_complete will handle cleanup and status

    def on_generation_complete(self, success):
        # --- PASTE on_generation_complete method here ---
        self.is_generating = False
        # Re-enable GUI elements
        self.toggle_gui_state(True)

        if success:
            # Status was already updated by run_generation on success
            # messagebox.showinfo("Success", "Video generation completed successfully!")
            pass # Status message is enough
        else:
            # Status was already updated by run_generation on error
            # An error message box was also likely shown
            pass # Error message box and status are enough

    def toggle_gui_state(self, enable):
        # --- PASTE toggle_gui_state method here ---
        state = tk.NORMAL if enable else tk.DISABLED
        # List of widgets to enable/disable
        widgets_to_toggle = [
            self.text_input_area,
            self.master.nametowidget(self.text_input_area.grid_info()['in']).grid_slaves(column=3, row=self.text_input_area.grid_info()['row'])[0], # The scrollbar
            self.master.nametowidget(self.text_input_area.grid_info()['in']).grid_slaves(column=1, row=self.text_input_area.grid_info()['row'] + 1)[0], # Load Text Button
            self.master.nametowidget(self.output_path.trace_info()[0][1]).grid_slaves(column=1, row=self.output_path.trace_info()[0][0])[0], # Output Entry (complex way)
            self.master.nametowidget(self.output_path.trace_info()[0][1]).grid_slaves(column=2, row=self.output_path.trace_info()[0][0])[0], # Output Browse Button (complex way)

            # Access widgets inside the notebook tabs
            self.master.nametowidget(self.fixed_dur_check.winfo_parent()).grid_slaves(row=self.fixed_dur_check.grid_info()['row'], column=self.fixed_dur_check.grid_info()['column'])[0], # fixed_dur_check
            self.master.nametowidget(self.fixed_dur_spinbox.winfo_parent()).grid_slaves(row=self.fixed_dur_spinbox.grid_info()['row'], column=self.fixed_dur_spinbox.grid_info()['column'])[0], # fixed_dur_spinbox
            # Add other widgets in video_frame
            self.master.nametowidget(self.width.trace_info()[0][1]).grid_slaves(row=0, column=1)[0], # Width Spinbox
            self.master.nametowidget(self.height.trace_info()[0][1]).grid_slaves(row=0, column=3)[0], # Height Spinbox
            self.master.nametowidget(self.fps.trace_info()[0][1]).grid_slaves(row=1, column=1)[0], # FPS Spinbox
            self.master.nametowidget(self.transition_duration.trace_info()[0][1]).grid_slaves(row=1, column=3)[0], # Transition Spinbox


            # Widgets in text_style_frame
            self.master.nametowidget(self.font_path.trace_info()[0][1]).grid_slaves(row=0, column=1)[0], # Font Path Entry
            self.master.nametowidget(self.font_path.trace_info()[0][1]).grid_slaves(row=0, column=2)[0], # Font Browse Button
            self.master.nametowidget(self.font_size.trace_info()[0][1]).grid_slaves(row=1, column=1)[0], # Font Size Spinbox
            self.text_color_button,
            self.bg_color_button,

            # Widgets in audio_frame
            self.tts_engine_combo,
            self.master.nametowidget(self.balcon_path.trace_info()[0][1]).grid_slaves(row=1, column=1)[0], # Balcon Path Entry
            self.master.nametowidget(self.balcon_path.trace_info()[0][1]).grid_slaves(row=1, column=2)[0], # Balcon Browse Button
            self.voice_combo,
            self.master.nametowidget(self.voice_combo.grid_info()['in']).grid_slaves(row=self.voice_combo.grid_info()['row'], column=2)[0], # Refresh Voices Button
            self.master.nametowidget(self.speed.trace_info()[0][1]).grid_slaves(row=3, column=1)[0], # Speed Spinbox

            # The Generate button itself
            self.master.nametowidget(self.status_label.grid_info()['in']).grid_slaves(row=self.status_label.grid_info()['row']+1, column=0)[0], # Generate Button (complex way)
        ]

        for widget in widgets_to_toggle:
            if widget: # Check if the widget was found
                try:
                    widget.config(state=state)
                except tk.TclError as e:
                    # Handle widgets that might not have a 'state' option (e.g., Labels)
                    # Or if the complex lookup failed
                    # print(f"Warning: Could not configure state for {widget}: {e}")
                    pass # Ignore if state config fails


# --- Main execution block ---
if __name__ == "__main__":
    # The auto-relaunch logic is placed before the GUI starts

    # If we reached here, either we are not on Windows,
    # or pythonw.exe was not found, or we are already running with pythonw.

    root = tk.Tk()
    app = TextToVideoApp(root)
    root.mainloop()