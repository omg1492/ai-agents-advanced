"""Process videos to infer product name and description using a vision-capable model.

Current status (2025-08-23): The public OpenAI Python SDK exposes image inputs via either
Chat Completions (beta.parse) or the unified Responses API. Direct raw *video* upload
(`type: input_video`) support is emerging but not yet consistently documented in the
stable SDK. This script implements a pragmatic fallback strategy:

Strategy:
1. Enumerate supported video files from `VIDEOS_INPUT_DIR` (default `../videos`).
2. For each video, extract a small set of representative frames (start, middle, end)
   using OpenCV (lightweight install) to create a concise visual summary without
   uploading the whole file. (We avoid full decoding for speed.)
3. Convert frames to base64 data URIs and send them as multiple `image_url` parts in a
   single vision prompt request (same pattern as images) asking the model to jointly
   infer a product name + description.
4. Produce structured output via a Pydantic model mirroring image script.

If/When native video inputs become generally available, we can replace the frame
sampling block with a direct `input_video` part; a clear TODO marker is left below.

Run:
  uv run process_video.py

Environment:
  OPENAI_API_KEY (required)
  OPENAI_MODEL (default gpt-5)
  OPENAI_BASE_URL / OPENAI_API_VERSION (Azure)
  VIDEOS_INPUT_DIR (optional path override)

Dependencies:
  - openai
  - python-dotenv
  - pydantic
  - opencv-python (added dynamically if missing; we attempt import and give guidance)

Output mirrors `process_images.py` including a consolidated summary block.
"""

from __future__ import annotations

import base64
import os
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

import cv2  # Expect opencv-python to be installed in the environment
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
 # (remote transcription dependencies removed)
from faster_whisper import WhisperModel


SUPPORTED_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm"}


class VideoProductSummary(BaseModel):
	"""Structured response for a single video (aggregated across sampled frames)."""

	product_name: str = Field(..., description="Concise product name inferred from the video")
	short_description: str = Field(
		..., description="2-3 sentence vivid, grounded description (appearance, inferred usage, key qualities)"
	)


def build_client() -> tuple[OpenAI, str]:
	"""Initialize OpenAI client supporting Azure variant via unified env vars."""
	load_dotenv()
	api_key = os.getenv("OPENAI_API_KEY")
	if not api_key:
		raise ValueError("OPENAI_API_KEY missing")
	base_url = os.getenv("OPENAI_BASE_URL")
	api_version = os.getenv("OPENAI_API_VERSION") or "2024-10-21"
	model = os.getenv("OPENAI_MODEL", "gpt-5")
	default_query = {"api-version": api_version} if base_url else None
	client = OpenAI(api_key=api_key, base_url=base_url, default_query=default_query)
	return client, model


_WHISPER_MODEL_SINGLETON: Optional[WhisperModel] = None


def get_whisper_model() -> WhisperModel:
	"""Lazy-load and cache the faster-whisper model based on env vars."""
	global _WHISPER_MODEL_SINGLETON  # noqa: PLW0603
	if _WHISPER_MODEL_SINGLETON is None:
		size = os.getenv("WHISPER_MODEL_SIZE", "small")
		compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
		_WHISPER_MODEL_SINGLETON = WhisperModel(size, device="cpu", compute_type=compute_type)
	return _WHISPER_MODEL_SINGLETON


def transcribe_audio_local(audio_path: Path) -> Tuple[Optional[str], Optional[str]]:  # pragma: no cover
	"""Transcribe audio using local faster-whisper only. Returns (text, error)."""
	try:
		model = get_whisper_model()
		beam_size = int(os.getenv("WHISPER_BEAM_SIZE", "5"))
		language = os.getenv("WHISPER_LANGUAGE") or None
		segments, info = model.transcribe(str(audio_path), beam_size=beam_size, language=language)
		text_parts: List[str] = []
		for seg in segments:
			if hasattr(seg, "text"):
				text_parts.append(seg.text.strip())
		if not text_parts:
			return None, "No segments returned by Whisper"
		transcript = " ".join(tp for tp in text_parts if tp)
		if not transcript:
			return None, "Empty transcript after joining segments"
		return transcript, None
	except Exception as e:  # noqa: BLE001
		return None, f"Local Whisper error: {e}"


def extract_audio_to_wav(video_path: Path) -> Tuple[Optional[Path], Optional[tempfile.TemporaryDirectory], Optional[str]]:  # pragma: no cover
	"""Extract mono 16k WAV audio track from video using ffmpeg.

	Returns (wav_path, tmp_dir_handle, error_message). Caller must cleanup tmp_dir_handle if not None.
	"""
	if not shutil.which("ffmpeg"):
		return None, None, "ffmpeg executable not found in PATH"
	tmp_dir = tempfile.TemporaryDirectory(prefix="vid_audio_")
	wav_path = Path(tmp_dir.name) / "audio.wav"
	cmd = [
		"ffmpeg",
		"-v",
		"error",
		"-i",
		str(video_path),
		"-vn",
		"-ac",
		"1",
		"-ar",
		"16000",
		"-f",
		"wav",
		str(wav_path),
	]
	try:
		proc = subprocess.run(cmd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
		if proc.returncode != 0 or not wav_path.exists():
			stderr_tail = (proc.stderr or "").strip().splitlines()[-5:]
			tmp_dir.cleanup()
			return None, None, f"ffmpeg failed (code {proc.returncode}): {' | '.join(stderr_tail)}"
	except Exception as e:  # noqa: BLE001
		tmp_dir.cleanup()
		return None, None, f"ffmpeg invocation error: {e}"
	return wav_path, tmp_dir, None


def frame_indices(frame_count: int, max_frames: int = 3) -> List[int]:
	"""Return up to `max_frames` indices spread across the video length."""
	if frame_count <= 0:
		return []
	if frame_count <= max_frames:
		return list(range(frame_count))
	# Evenly spaced including first/last
	return [int(i * (frame_count - 1) / (max_frames - 1)) for i in range(max_frames)]


def extract_sample_frames(path: Path, max_frames: int = 3) -> tuple[List[bytes], List[int], int]:
	"""Extract a small set of representative frames as raw JPEG bytes.

	Returns (frames_bytes, selected_indices, total_frame_count).
	"""
	cap = cv2.VideoCapture(str(path))
	if not cap.isOpened():
		raise RuntimeError(f"Failed to open video: {path}")
	frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
	selected = frame_indices(frame_count, max_frames=max_frames)
	target_indices = set(selected)
	frames: List[bytes] = []
	idx = 0
	success, frame = cap.read()
	while success and target_indices:
		if idx in target_indices:
			ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
			if ok:
				frames.append(buf.tobytes())
			target_indices.remove(idx)
		idx += 1
		success, frame = cap.read()
	cap.release()
	return frames, selected, frame_count


def bytes_to_data_uri(data: bytes) -> str:
	"""Encode JPEG bytes to a data URI."""
	b64 = base64.b64encode(data).decode("utf-8")
	return f"data:image/jpeg;base64,{b64}"


def summarize_video(client: OpenAI, model: str, path: Path) -> Dict[str, Any]:
	"""Summarize a video by sampling frames and sending them as multiple image parts.

	NOTE: Replace with native video input once stable (TODO: support direct `input_video`).
	"""
	frames, indices, total_frames = extract_sample_frames(path, max_frames=3)
	if not frames:
		raise RuntimeError("No frames extracted")
	print_block(
		"FRAME SAMPLING",
		f"Total frames in video: {total_frames}\nSelected indices: {indices}\nExtracted frame count: {len(frames)}",
	)
	image_parts = [
		{"type": "image_url", "image_url": {"url": bytes_to_data_uri(f)}} for f in frames
	]

	# Attempt audio extraction + transcription (best-effort with diagnostics)
	wav_path, tmp_dir_handle, audio_err = extract_audio_to_wav(path)
	transcript_text: Optional[str] = None
	transcribe_err: Optional[str] = None
	if wav_path and not audio_err:
		transcript_text, transcribe_err = transcribe_audio_local(wav_path)
		try:
			if tmp_dir_handle:
				tmp_dir_handle.cleanup()
		except Exception:  # noqa: BLE001
			pass

	if audio_err:
		print_block("AUDIO EXTRACTION", f"Failed: {audio_err}")
	elif wav_path:
		print_block("AUDIO EXTRACTION", f"Success: extracted WAV at 16kHz -> {wav_path.name}")

	if transcript_text:
		print_block(
			"TRANSCRIPTION",
			f"Success: {len(transcript_text)} chars\nPreview (first 240 chars):\n{transcript_text[:240]}",
		)
	else:
		if transcribe_err:
			print_block("TRANSCRIPTION", f"Failed: {transcribe_err}")
		else:
			print_block("TRANSCRIPTION", "No transcription available (no audio track detected)")

	system_prompt = (
		"You analyze short product-related farm or food videos. Using the provided sampled frames, "
		"infer a concise product name and a grounded description. If uncertainty remains, choose the most plausible concise name."
	)
	user_instruction = (
		"Analyze these frames (chronological order) representing a short video and extract: product_name (concise) and short_description (2-3 sentences). "
		"Ground description in visible evidence: form, color, packaging, context cues. Avoid speculation beyond frames."
	)
	if transcript_text:
		user_instruction += (
			"\n\nFull transcript (may aid identification, ignore irrelevant narration):\n" + transcript_text
		)
	response = client.beta.chat.completions.parse(
		model=model,
		messages=[
			{"role": "system", "content": system_prompt},
			{"role": "user", "content": [{"type": "text", "text": user_instruction}, *image_parts]},
		],
		response_format=VideoProductSummary,
	)
	parsed: VideoProductSummary = response.choices[0].message.parsed  # type: ignore[attr-defined]
	return parsed.model_dump()


def print_block(title: str, body: str) -> None:
	line = "=" * 90
	print(f"\n{line}\n{title}\n{line}\n{body}\n{line}\n")


def main() -> int:
	try:
		client, model = build_client()
		base_dir = Path(__file__).parent
		videos_dir = Path(os.getenv("VIDEOS_INPUT_DIR") or (base_dir / "../videos").resolve())
		if not videos_dir.exists():
			raise FileNotFoundError(f"Videos directory not found: {videos_dir}")
		files = [p for p in sorted(videos_dir.iterdir()) if p.suffix.lower() in SUPPORTED_VIDEO_EXT and p.is_file()]
		if not files:
			print(f"No supported video files in {videos_dir}")
			return 0
		summaries: List[Dict[str, Any]] = []
		for vid in files:
			print_block("PROCESSING VIDEO", f"File: {vid.name}")
			try:
				summary = summarize_video(client, model, vid)
				body = (
					f"Product Name: {summary['product_name']}\n\n"
					f"Description:\n{summary['short_description']}"
				)
				print_block("LLM SUMMARY", body)
				summaries.append({"file": vid.name, **summary})
			except Exception as e:  # continue on error
				print_block("ERROR", f"Failed processing {vid.name}: {e}")
		if summaries:
			lines = []
			for i, s in enumerate(summaries, start=1):
				lines.append(
					f"{i}. {s['product_name']} (source: {s['file']})\n"
					f"   {s['short_description'].strip()}\n"
				)
			print_block("CONSOLIDATED VIDEO PRODUCT SUMMARIES", "\n".join(lines))
		return 0
	except Exception as outer:  # noqa: BLE001
		print(f"Fatal error: {outer}", file=sys.stderr)
		return 1


if __name__ == "__main__":  # pragma: no cover
	raise SystemExit(main())

