# editor.py
import os
import asyncio
import logging
from typing import List, Dict, Coroutine
from uploader import Uploader

logger = logging.getLogger(__name__)

class Editor:
    def __init__(
        self,
        cookies_file: str,
        hw_accel: str = "cuda",
        segment_length: int = 180,
        output_dir: str = "clips",
        max_concurrent_tasks: int = 3
    ):
        self.hw_accel = hw_accel.lower()
        self.segment_length = segment_length
        self.output_dir = output_dir
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.uploader = Uploader(cookies_file)
        self._validate_hw_accel()
        
        os.makedirs(self.output_dir, exist_ok=True)
        logger.info(f"Initialized Editor with {hw_accel} acceleration")

    def _validate_hw_accel(self):
        valid_methods = ["vdpau", "cuda", "vaapi", "qsv", "drm", "opencl", "vulkan"]
        if self.hw_accel not in valid_methods:
            raise ValueError(f"Invalid HW acceleration. Choose from: {', '.join(valid_methods)}")

    async def _segment_exists(self, output_path: str, expected_duration: float) -> bool:
        """Check if valid segment exists"""
        try:
            if not os.path.exists(output_path):
                return False

            actual_duration = await self._get_video_duration(output_path)
            return abs(actual_duration - expected_duration) < 1.0
            
        except Exception as e:
            logger.warning(f"Segment check failed: {str(e)}")
            return False

    async def _get_video_duration(self, video_path: str) -> float:
        """Get duration using ffprobe"""
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        return float(stdout.decode().strip())

    async def _log_stream(self, stream, logger_func):
        """Real-time FFmpeg logging"""
        while True:
            line = await stream.readline()
            if not line:
                break
            logger_func(line.decode().strip())

    async def _process_segment(
        self,
        video_path: str,
        start: float,
        duration: float,
        main_text: str,
        part_info: str,
        output_path: str,
        description: str
    ) -> str:
        """Process video segment with GPU acceleration"""
        async with self.semaphore:
            try:
                # Check existing segment
                if await self._segment_exists(output_path, duration):
                    logger.info(f"Reusing existing segment: {output_path}")
                    return await self.uploader.upload(output_path, description)

                # FFmpeg GPU command setup
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-loglevel', 'verbose',
                    '-hwaccel', 'cuda',
                    '-hwaccel_output_format', 'cuda',
                    '-extra_hw_frames', '2',
                    '-ss', str(start),
                    '-i', video_path,
                    '-t', str(duration),
                    '-vf', (
                        f"format=yuv420p,"
                        f"scale_cuda=1280:720,"
                        f"drawtext=text='{main_text[:2200]}':"
                        f"fontsize=70:fontcolor=white:font='Arial-Bold':"
                        f"borderw=1:bordercolor=black:x=(w-text_w)/2:y=h*0.08,"
                        f"drawtext=text='{part_info}':"
                        f"fontsize=60:fontcolor=white:font='Arial-Bold':"
                        f"borderw=1:bordercolor=black:x=(w-text_w)/2:y=h-h*0.08-60"
                    ),
                    '-c:v', 'libx264',
                    '-preset', 'veryfast',
                    '-movflags', '+faststart',
                    '-c:a', 'aac',
                    '-b:a', '128k',
                    '-y',
                    output_path
                ]

                # Execute FFmpeg
                proc = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                # Logging
                stdout_task = asyncio.create_task(self._log_stream(proc.stdout, logger.debug))
                stderr_task = asyncio.create_task(self._log_stream(proc.stderr, logger.info))

                await proc.wait()
                await stdout_task
                await stderr_task

                if proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed with code {proc.returncode}")

                return await self.uploader.upload(output_path, description)

            except Exception as e:
                logger.error(f"Processing failed: {str(e)}")
                raise
            finally:
                if os.path.exists(output_path) and os.path.getsize(output_path) == 0:
                    os.remove(output_path)

    async def crop_video_to_clips(self, video: Dict) -> List[Coroutine]:
        """Generate video segments"""
        try:
            video_path = video['video_path']
            total_duration = await self._get_video_duration(video_path)
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_folder = os.path.join(self.output_dir, f"{base_name}_segments")
            os.makedirs(output_folder, exist_ok=True)

            tasks = []
            for i in range(0, int(total_duration), self.segment_length):
                start = i
                end = min(i + self.segment_length, total_duration)
                duration = end - start
                part_num = (i // self.segment_length) + 1
                total_parts = (int(total_duration) // self.segment_length) + 1
                
                # Format description
                part_suffix = f" (Part {part_num}/{total_parts})"
                clean_title = video['title'].strip()[:2200 - len(part_suffix)]
                description = f"{clean_title}{part_suffix}"
                
                output_path = os.path.join(output_folder, f"part_{part_num}.mp4")
                part_info = f"Part {part_num}/{total_parts}"

                tasks.append(
                    self._process_segment(
                        video_path=video_path,
                        start=start,
                        duration=duration,
                        main_text=video['title'],
                        part_info=part_info,
                        output_path=output_path,
                        description=description
                    )
                )
            return tasks
            
        except Exception as e:
            logger.error(f"Video processing failed: {str(e)}")
            raise