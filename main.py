# main.py
import asyncio
import logging
import json
import os
from downloader import Downloader
from editor import Editor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

async def main():
    # Load configuration
    with open('config.json', 'r') as config_file:
        config = json.load(config_file)
    
    # Setup working directory
    working_dir = "/tmp/yt"
    os.makedirs(working_dir, exist_ok=True)
    logger.info(f"Using working directory: {working_dir}")

    # Initialize components
    downloader = Downloader(output_dir=working_dir)
    editor = Editor(
        cookies_file=config['cookies_file'],
        segment_length=config.get('segment_length', 180),
        output_dir=working_dir,
        max_concurrent_tasks=config.get('max_concurrent_tasks', 3)
    )

    try:
        # Step 1: Get channel videos
        videos = await downloader.get_channel_videos(
            config['channel_url'],
            limit=config.get('video_limit', 5)
        )
        
        # Step 2: Process and upload videos
        upload_tasks = []
        for video in videos:
            try:
                # Download video
                downloaded_video = await downloader.download_video(video)
                if not downloaded_video:
                    continue
                
                # Process and upload segments
                segment_tasks = await editor.crop_video_to_clips(downloaded_video)
                await asyncio.gather(*segment_tasks)
                
                # Cleanup original video
                
            except Exception as e:
                logger.error(f"Error processing video {video['id']}: {str(e)}")
                continue
        
        # Wait for all uploads to complete
        if upload_tasks:
            await asyncio.gather(*upload_tasks)
            
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
    finally:
        # Cleanup working directory
        for root, dirs, files in os.walk(working_dir, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))
        logger.info("Cleanup completed")

if __name__ == "__main__":
    asyncio.run(main())