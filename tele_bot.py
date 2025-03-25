import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import instaloader
import os
from urllib.parse import urlparse
import re
import logging
import yt_dlp

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace 'YOUR_BOT_TOKEN' with your actual Telegram bot token
TOKEN = ''

# Initialize the bot
updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher

# Initialize Instaloader
L = instaloader.Instaloader()

# Function to check if the URL is a valid Instagram URL
def is_instagram_url(url):
    pattern = r'(https?://(www\.)?instagram\.com/(p|reel|tv)/[A-Za-z0-9_-]+)'
    return re.match(pattern, url) is not None

# Function to check if the URL is a valid YouTube URL
def is_youtube_url(url):
    pattern = r'(https?://(www\.)?(youtube\.com|youtu\.be)/(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11}))'
    return re.match(pattern, url) is not None

# Function to check if the URL is a valid Facebook URL
def is_facebook_url(url):
    pattern = r'(https?://(www\.)?(facebook\.com|fb\.watch)/.*)'
    return re.match(pattern, url) is not None

# Function to download Instagram video
def download_instagram_video(url):
    try:
        shortcode = urlparse(url).path.split('/')[2]
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        if post.is_video:
            L.download_post(post, target='downloads')
            for file in os.listdir('downloads'):
                if file.endswith('.mp4'):
                    video_path = os.path.join('downloads', file)
                    return video_path
            return None
        else:
            return None
    except Exception as e:
        logger.error(f"Error downloading video: {str(e)}")
        return None

# Function to download YouTube or Facebook video using yt-dlp
def download_youtube_facebook_video(url):
    try:
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'noplaylist': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')
            for file in os.listdir('downloads'):
                if file.endswith('.mp4'):
                    video_path = os.path.join('downloads', file)
                    return video_path
            return None
    except yt_dlp.utils.DownloadError as e:
        if "ffmpeg is not installed" in str(e):
            logger.warning("ffmpeg not found, falling back to single stream download")
            ydl_opts = {
                'format': 'best[ext=mp4]',
                'outtmpl': 'downloads/%(title)s.%(ext)s',
                'noplaylist': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get('title', 'video')
                for file in os.listdir('downloads'):
                    if file.endswith('.mp4'):
                        video_path = os.path.join('downloads', file)
                        return video_path
                return None
        else:
            logger.error(f"Error downloading YouTube/Facebook video: {str(e)}")
            return None
    except Exception as e:
        logger.error(f"Error downloading YouTube/Facebook video: {str(e)}")
        return None

# Start command handler
def start(update, context):
    update.message.reply_text(
        "Hello! I'm your video downloader bot. Just send me a video link from Instagram, YouTube, or Facebook (post, reel, or video), and I'll send you the downloadable video!"
    )

# Message handler for processing URLs
def handle_message(update, context):
    message_text = update.message.text
    
    if is_instagram_url(message_text):
        update.message.reply_text("Processing your Instagram link... Please wait!")
        video_path = download_instagram_video(message_text)
    elif is_youtube_url(message_text):
        update.message.reply_text("Processing your YouTube link... Please wait!")
        video_path = download_youtube_facebook_video(message_text)
    elif is_facebook_url(message_text):
        update.message.reply_text("Processing your Facebook link... Please wait!")
        video_path = download_youtube_facebook_video(message_text)
    else:
        update.message.reply_text(
            "Hmm, that doesn’t look like a valid Instagram, YouTube, or Facebook video link! Please send a proper URL (e.g., https://www.instagram.com/p/XXXXX/, https://www.youtube.com/watch?v=XXXXX, or https://www.facebook.com/XXXXX/videos/XXXXX/), and I’ll get that video for you!"
        )
        return
    
    if video_path:
        try:
            file_size = os.path.getsize(video_path) / (1024 * 1024)
            logger.info(f"Video downloaded: {video_path}, Size: {file_size:.2f} MB")
            
            if file_size > 50:
                update.message.reply_text(
                    f"The video is too large ({file_size:.2f} MB)! Telegram has a 50 MB limit for bots. Please try a smaller video."
                )
                return
            
            with open(video_path, 'rb') as video:
                update.message.reply_video(video)
            
            try:
                for file in os.listdir('downloads'):
                    file_path = os.path.join('downloads', file)
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                if os.path.exists('downloads') and not os.listdir('downloads'):
                    os.rmdir('downloads')
                logger.info("Cleaned up downloads folder successfully")
            except Exception as e:
                logger.error(f"Error during cleanup: {str(e)}")
                update.message.reply_text(
                    "Video sent, but I had trouble cleaning up the temporary files. Please try again!"
                )
            
            update.message.reply_text("Here’s your video! Enjoy!")
        except Exception as e:
            logger.error(f"Error sending video: {str(e)}")
            update.message.reply_text(
                "I downloaded the video, but something went wrong while sending it. The video might be too large (Telegram has a 50 MB limit for bots). Please try a smaller video!"
            )
    else:
        update.message.reply_text(
            "Oops! It seems like that link doesn’t contain a video or something went wrong. Could you please send a valid Instagram, YouTube, or Facebook video URL? I’d love to help you out!"
        )

# Error handler
def error(update, context):
    logger.error(f"Update {update} caused error {context.error}")
    update.message.reply_text(
        "Oh no! Something went wrong on my end. Could you try again?"
    )

# Add handlers
dp.add_handler(CommandHandler("start", start))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
dp.add_error_handler(error)

# Create downloads directory if it doesn't exist
if not os.path.exists('downloads'):
    os.makedirs('downloads')

# Start the bot
print("Bot is running...")
updater.start_polling()
updater.idle()