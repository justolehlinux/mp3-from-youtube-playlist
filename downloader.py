import os
import yt_dlp
import logging
import asyncio
import json

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Загрузка конфигурации
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

class Downloader:
    def __init__(self, output_dir="downloads", video_format="bestvideo[height<=1080]+bestaudio/best"):
        self.output_dir = output_dir
        self.video_format = video_format
        os.makedirs(self.output_dir, exist_ok=True)

    async def get_channel_videos(self, channel_url, limit):
        """Retrieve video metadata from a YouTube channel or playlist."""
        logger.info("Retrieving videos from channel URL...")
        ydl_opts = {
            # 'format': self.video_format,
            'outtmpl': os.path.join(self.output_dir, '%(id)s', '%(title)s.%(ext)s'),
            'playlistend': limit,
            'quiet': False,
            'extract_flat': True,  # Only retrieve metadata, don't download videos
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            channel_info = ydl.extract_info(channel_url, download=False)
            return channel_info['entries'] if 'entries' in channel_info else [channel_info]
        
    async def download_video(self, video_info):
        """Download a single video using yt-dlp."""
        try:
            ydl_opts = {
                'format': self.video_format,
                'outtmpl': os.path.join(self.output_dir, '%(title)s', '%(title)s.%(ext)s'),
                'quiet': False,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_info['url'], download=True)
                video_path = ydl.prepare_filename(info)
                description = f"{info['title']} {info.get('channel', '')} {info.get('description', '')[-1800:]}"
                duration = info['duration']
                title = f"{info['title']}"
                return {
                    'video_path': video_path,
                    'title': title,
                    'description': description,
                    'duration': duration,
                }
        except Exception as e:
            logger.error(f"Error downloading video '{video_info.get('title', 'Unknown')}': {str(e)}")
            return None


async def download_videos_from_channel(channel_url, num_videos):
    

    # format = "bestvideo[vcodec=h264][height<=?1080][ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]",            
    # downloader = Downloader(video_format=format)
    
    downloader = Downloader()
                                
    # Get video metadata for the specified number of videos
    videos_metadata = await downloader.get_channel_videos(channel_url, limit=num_videos)
    
    # Define an async download task for each video
    download_tasks = [
        downloader.download_video(video)
        for video in videos_metadata
    ]
    
    # Run download tasks concurrently and collect results
    downloaded_videos = await asyncio.gather(*download_tasks)

    # Filter out any None results from failed downloads and create the output dictionary
    return [
        video_info for video_info in downloaded_videos if video_info is not None
    ]

# Usage example
async def main():
    # Example YouTube channel URL
    url = config['channel_url']  
    num_videos = 2
    
    # URL can be a channel or a video link    num_videos = 3  # Specify the number of videos to download
    
    downloaded_videos = await download_videos_from_channel(url, num_videos)
    
    for video in downloaded_videos:
        print(f"Video Path: {video['video_path']}")
        print(f"Description: {video['description']}")
        print("------------")

if __name__ == "__main__":
    asyncio.run(main())
