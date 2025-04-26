import logging
import argparse
from tiktok_uploader import tiktok, Video
from tiktok_uploader.basics import eprint
from tiktok_uploader.Config import Config
import sys
import os

# Set up logging
logger = logging.getLogger(__name__)

class Uploader:
    def __init__(self, users):
        self.users = users
        self.cookies_file = os.path.join(
            os.getcwd(), 
            Config.get().cookies_dir, 
            f'tiktok_session-{users}'
        )

    def upload_video(
        self, 
        video_path, 
        title, 
        schedule=0, 
        comment=1, 
        duet=0, 
        stitch=0, 
        visibility=0, 
        brandorganic=0, 
        brandcontent=0, 
        ailabel=0, 
        proxy=""
    ):
        """Uploads a video using TikTok API"""
        video_full_path = os.path.join(
            os.getcwd(), 
            Config.get().videos_dir, 
            video_path
        )
        
        if not os.path.exists(video_full_path):
            print("[-] Video does not exist")
            print("Available videos:")
            for name in os.listdir(os.path.dirname(video_full_path)):
                print(f'[-] {name}')
            sys.exit(1)

        try:
            tiktok.upload_video(
                self.users,
                video_full_path,
                title,
                schedule,
                comment,
                duet,
                stitch,
                visibility,
                brandorganic,
                brandcontent,
                ailabel,
                proxy
            )
            print(video_full_path + ": Finish")
            
        except Exception as e:
            logger.error(f"Upload failed: {str(e)}")
            sys.exit(1)

if __name__ == "__main__":
    _ = Config.load("./config.txt")
    
    parser = argparse.ArgumentParser(
        description="TikTokAutoUpload CLI for managing uploads"
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # Login command
    login_parser = subparsers.add_parser(
        "login", 
        help="Authenticate and save session cookies"
    )
    login_parser.add_argument(
        "-n", 
        "--name", 
        required=True, 
        help="Name to save cookie session as"
    )

    # Upload command
    upload_parser = subparsers.add_parser(
        "upload", 
        help="Upload video to TikTok"
    )
    upload_parser.add_argument(
        "-u", 
        "--users", 
        required=True, 
        help="Cookie name from login"
    )
    upload_parser.add_argument(
        "-v", 
        "--video", 
        help="Path to video file"
    )
    upload_parser.add_argument(
        "-yt", 
        "--youtube", 
        help="YouTube URL to download video from"
    )
    upload_parser.add_argument(
        "-t", 
        "--title", 
        required=True, 
        help="Video title/description"
    )
    upload_parser.add_argument(
        "-sc", 
        "--schedule", 
        type=int, 
        default=0, 
        help="Schedule timestamp (seconds)"
    )
    upload_parser.add_argument(
        "-ct", 
        "--comment", 
        type=int, 
        default=1, 
        choices=[0, 1]
    )
    upload_parser.add_argument(
        "-d", 
        "--duet", 
        type=int, 
        default=0, 
        choices=[0, 1]
    )
    upload_parser.add_argument(
        "-st", 
        "--stitch", 
        type=int, 
        default=0, 
        choices=[0, 1]
    )
    upload_parser.add_argument(
        "-vi", 
        "--visibility", 
        type=int, 
        default=0, 
        help="0 = public, 1 = private"
    )
    upload_parser.add_argument(
        "-bo", 
        "--brandorganic", 
        type=int, 
        default=0
    )
    upload_parser.add_argument(
        "-bc", 
        "--brandcontent", 
        type=int, 
        default=0
    )
    upload_parser.add_argument(
        "-ai", 
        "--ailabel", 
        type=int, 
        default=0
    )
    upload_parser.add_argument(
        "-p", 
        "--proxy", 
        default="", 
        help="Proxy server address"
    )

    # Show command
    show_parser = subparsers.add_parser(
        "show", 
        help="List available resources"
    )
    show_parser.add_argument(
        "-u", 
        "--users", 
        action="store_true", 
        help="Show authenticated users"
    )
    show_parser.add_argument(
        "-v", 
        "--videos", 
        action="store_true", 
        help="Show available videos"
    )

    args = parser.parse_args()

    if args.subcommand == "login":
        tiktok.login(args.name)

    elif args.subcommand == "upload":
        if not args.video and not args.youtube:
            eprint("Error: No video source provided")
            sys.exit(1)
        if args.video and args.youtube:
            eprint("Error: Cannot use both video and YouTube flags")
            sys.exit(1)

        if args.youtube:
            video = Video(args.youtube, args.title)
            video.is_valid_file_format()
            video_path = video.source_ref
        else:
            video_path = args.video

        uploader = Uploader(args.users)
        uploader.upload_video(
            video_path=video_path,
            title=args.title,
            schedule=args.schedule,
            comment=args.comment,
            duet=args.duet,
            stitch=args.stitch,
            visibility=args.visibility,
            brandorganic=args.brandorganic,
            brandcontent=args.brandcontent,
            ailabel=args.ailabel,
            proxy=args.proxy
        )

    elif args.subcommand == "show":
        if args.users:
            print("Authenticated Users:")
            cookie_dir = os.path.join(
                os.getcwd(), 
                Config.get().cookies_dir
            )
            for f in os.listdir(cookie_dir):
                if f.startswith("tiktok_session-"):
                    print(f"- {f.split('tiktok_session-')[1]}")
        elif args.videos:
            print("Available Videos:")
            video_dir = os.path.join(
                os.getcwd(), 
                Config.get().videos_dir
            )
            for f in os.listdir(video_dir):
                print(f"- {f}")
        else:
            print("Specify -u for users or -v for videos")

    else:
        eprint("Invalid command. Use login, upload, or show.")