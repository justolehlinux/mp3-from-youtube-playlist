# editor.py
import os
import asyncio
import logging
from typing import List, Dict, Coroutine
from uploader import Uploader

logger = logging.getLogger(__name__)

class Editor:
    def __init__(self, 
                 cookies_file: str, 
                 segment_length: int = 180,
                 output_dir: str = "clips",
                 max_concurrent_tasks: int = 3):
        self.segment_length = segment_length
        self.output_dir = output_dir
        self.max_concurrent_tasks = max_concurrent_tasks
        self.semaphore = asyncio.Semaphore(max_concurrent_tasks)
        self.uploader = Uploader("my_saved_username")
        os.makedirs(self.output_dir, exist_ok=True)
    
    async def _segment_exists(self, output_path: str, expected_duration: float) -> bool:
        """Check if segment exists and has valid duration"""
        try:
            if not os.path.exists(output_path):
                return False

            actual_duration = await self._get_video_duration(output_path)
            duration_diff = abs(actual_duration - expected_duration)
            
            logger.debug(f"Segment check: {output_path}")
            logger.debug(f"Expected duration: {expected_duration:.2f}s, Actual: {actual_duration:.2f}s")
            
            return duration_diff < 1.0  # Allow 1 second difference
            
        except Exception as e:
            logger.warning(f"Segment check failed for {output_path}: {str(e)}")
            return False
   
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
        """Process a video segment with FFmpeg and upload"""
        async with self.semaphore:
            try:
                
                # Check if valid segment already exists
                if await self._segment_exists(output_path, duration):
                    logger.info(f"Using existing segment: {output_path}")
                    return await self.uploader.upload(
                        video_path=output_path,
                        description=description
                    )
                # Escape special characters in text
                main_text_escaped = main_text.replace("'", r"\'")[:50]
                part_info_escaped = part_info.replace("'", r"\'")
                print(part_info_escaped + ": STARTED")

                # Build FFmpeg command
                ffmpeg_cmd = [
                    'ffmpeg',
                    '-loglevel', 'verbose',  # Enable verbose logging
                    '-ss', str(start),
                    '-i', video_path,
                    '-t', str(duration),
                    '-vf',
                    f"drawtext=text='{main_text_escaped}':"
                    f"fontsize=70:fontcolor=white:font='Arial-Bold':"
                    f"borderw=1:bordercolor=black:x=(w-text_w)/2:y=h*0.08,"
                    f"drawtext=text='{part_info_escaped}':"
                    f"fontsize=60:fontcolor=white:font='Arial-Bold':"
                    f"borderw=1:bordercolor=black:x=(w-text_w)/2:y=h-h*0.08-60",
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-c:a', 'aac',
                    '-threads', '4',
                    '-y',
                    output_path
                ]

                # Execute FFmpeg command
                proc = await asyncio.create_subprocess_exec(
                    *ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

                if proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed with exit code {proc.returncode}")

                print(part_info_escaped + ": UPLOADED")
                
                # Upload processed segment
                return await self.uploader.upload_video(
                    video_path=output_path,
                    title=description
                )
                
                
            except Exception as e:
                logger.error(f"Segment processing failed: {str(e)}")
                raise

    async def crop_video_to_clips(self, video: Dict) -> List[Coroutine]:
        """Split video into segments and create upload tasks"""
        try:
            video_path = video['video_path']
            total_duration = video['duration']
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            output_folder = os.path.join(self.output_dir, f"{base_name}_segments")
            os.makedirs(output_folder, exist_ok=True)
            print(output_folder + ": FOLDER created")
            
            tasks = []
            for i in range(0, int(total_duration), self.segment_length):
                start = i
                end = min(i + self.segment_length + 1, total_duration)
                duration = end - start
                part_num = (i // self.segment_length) + 1
                total_parts = (int(total_duration) // self.segment_length) + 1
                
                output_path = os.path.join(output_folder, f"part_{part_num}.mp4")
                description = f"(Part {part_num}/{total_parts}) {video['description']}"
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