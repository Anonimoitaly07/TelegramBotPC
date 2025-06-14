#!/usr/bin/env python3
"""
Telegram PC Remote Control Bot
=============================

A comprehensive Telegram bot for remote PC control with interactive buttons.
Compatible with Windows and Linux systems.

Requirements:
- Python 3.7+
- Telegram Bot Token
- Admin Chat ID

Author: Claude Assistant
Version: 1.0
"""

import os
import sys
import time
import logging
import threading
import subprocess
import platform
import shutil
import tempfile
from datetime import datetime, time as dt_time
from pathlib import Path
import json

# Third-party imports
try:
    import psutil
    import pyautogui
    import cv2
    import sounddevice as sd
    import numpy as np
    import schedule
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
    import asyncio
except ImportError as e:
    print(f"Missing required library: {e}")
    print("Please install requirements using: pip install -r requirements.txt")
    sys.exit(1)

# =============================================================================
# CONFIGURATION
# =============================================================================

# Bot Configuration - CHANGE THESE VALUES
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"  # Get from @BotFather on Telegram
ADMIN_CHAT_ID = "YOUR_CHAT_ID_HERE"  # Your Telegram chat ID (as string)

# File paths
LOG_FILE = "bot_log.txt"
CONFIG_FILE = "bot_config.json"

# Audio recording settings
AUDIO_DURATION = 10  # seconds
AUDIO_SAMPLE_RATE = 44100

# =============================================================================
# LOGGING SETUP
# =============================================================================

def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()

# =============================================================================
# USB MONITOR CLASS
# =============================================================================

class USBMonitor(FileSystemEventHandler):
    """Monitor USB device insertions"""
    
    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.last_devices = set(self.get_usb_devices())
    
    def get_usb_devices(self):
        """Get list of current USB devices"""
        devices = set()
        try:
            if platform.system() == "Windows":
                # Windows USB detection using psutil
                partitions = psutil.disk_partitions()
                for partition in partitions:
                    if 'removable' in partition.opts:
                        devices.add(partition.device)
            else:
                # Linux - check /media and /mnt
                for mount_point in ['/media', '/mnt', '/run/media']:
                    if os.path.exists(mount_point):
                        try:
                            for user_dir in os.listdir(mount_point):
                                user_path = os.path.join(mount_point, user_dir)
                                if os.path.isdir(user_path):
                                    for device in os.listdir(user_path):
                                        devices.add(os.path.join(user_path, device))
                        except PermissionError:
                            pass
                        except FileNotFoundError:
                            pass
        except Exception as e:
            logger.error(f"Error getting USB devices: {e}")
        return devices

# =============================================================================
# MAIN BOT CLASS
# =============================================================================

class PCControlBot:
    """Main Telegram bot class for PC remote control"""
    
    def __init__(self):
        self.app = None
        self.usb_monitor = USBMonitor(self)
        self.observer = Observer()
        
    async def send_notification(self, message):
        """Send notification to admin"""
        try:
            if self.app and hasattr(self.app, 'bot'):
                await self.app.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message)
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def log_action(self, action, details=""):
        """Log bot actions"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_message = f"[{timestamp}] {action}"
        if details:
            log_message += f" - {details}"
        logger.info(log_message)
    
    def is_admin(self, user_id):
        """Check if user is admin"""
        return str(user_id) == str(ADMIN_CHAT_ID)
    
    def get_main_keyboard(self):
        """Create main menu keyboard"""
        keyboard = [
            [
                InlineKeyboardButton("📸 Screenshot", callback_data="screenshot"),
                InlineKeyboardButton("🧠 System Status", callback_data="system_status")
            ],
            [
                InlineKeyboardButton("🖥️ Run Command", callback_data="run_command"),
                InlineKeyboardButton("🧾 File List", callback_data="file_list")
            ],
            [
                InlineKeyboardButton("📂 Send File", callback_data="send_file"),
                InlineKeyboardButton("🔊 Record Audio", callback_data="record_audio")
            ],
            [
                InlineKeyboardButton("🎥 Webcam", callback_data="webcam"),
                InlineKeyboardButton("💾 System Report", callback_data="system_report")
            ],
            [
                InlineKeyboardButton("⏻ Shutdown", callback_data="shutdown"),
                InlineKeyboardButton("🔁 Restart", callback_data="restart")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ Unauthorized access denied.")
            self.log_action("UNAUTHORIZED_ACCESS", f"User ID: {user_id}")
            return
        
        self.log_action("START_COMMAND", f"Admin connected: {user_id}")
        
        welcome_message = (
            f"🤖 **PC Remote Control Bot**\n\n"
            f"🖥️ System: {platform.system()} {platform.release()}\n"
            f"💻 Node: {platform.node()}\n"
            f"⏰ Online since: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"Select an option from the menu below:"
        )
        
        await update.message.reply_text(
            welcome_message,
            reply_markup=self.get_main_keyboard(),
            parse_mode='Markdown'
        )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        user_id = query.from_user.id
        
        if not self.is_admin(user_id):
            await query.answer("❌ Unauthorized access denied.")
            return
        
        await query.answer()
        action = query.data
        
        self.log_action("BUTTON_PRESSED", action)
        
        # Handle different button actions
        if action == "screenshot":
            await self.take_screenshot(query)
        elif action == "system_status":
            await self.get_system_status(query)
        elif action == "run_command":
            await self.prompt_run_command(query)
        elif action == "file_list":
            await self.prompt_file_list(query)
        elif action == "send_file":
            await self.prompt_send_file(query)
        elif action == "record_audio":
            await self.record_audio(query)
        elif action == "webcam":
            await self.take_webcam_photo(query)
        elif action == "system_report":
            await self.generate_system_report(query)
        elif action == "shutdown":
            await self.shutdown_pc(query)
        elif action == "restart":
            await self.restart_pc(query)
    
    async def take_screenshot(self, query):
        """Take and send screenshot"""
        try:
            await query.edit_message_text("📸 Taking screenshot...")
            
            # Take screenshot
            screenshot = pyautogui.screenshot()
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                screenshot.save(tmp_file.name)
                tmp_path = tmp_file.name
            
            # Send screenshot
            with open(tmp_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=f"📸 Screenshot taken at {datetime.now().strftime('%H:%M:%S')}",
                    reply_markup=self.get_main_keyboard()
                )
            
            # Clean up
            os.unlink(tmp_path)
            await query.message.delete()
            
            self.log_action("SCREENSHOT_TAKEN")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error taking screenshot: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("SCREENSHOT_ERROR", str(e))
    
    async def get_system_status(self, query):
        """Get and send system status"""
        try:
            # Get system information
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Get uptime
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            # Format uptime
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{days}d {hours}h {minutes}m"
            
            status_message = (
                f"🧠 **System Status**\n\n"
                f"💾 **Memory Usage:**\n"
                f"├ Used: {memory.used // (1024**3):.1f} GB ({memory.percent}%)\n"
                f"└ Total: {memory.total // (1024**3):.1f} GB\n\n"
                f"🖥️ **CPU Usage:** {cpu_percent}%\n\n"
                f"💿 **Disk Usage:**\n"
                f"├ Used: {disk.used // (1024**3):.1f} GB ({disk.used/disk.total*100:.1f}%)\n"
                f"└ Free: {disk.free // (1024**3):.1f} GB\n\n"
                f"⏰ **Uptime:** {uptime_str}\n"
                f"🖥️ **OS:** {platform.system()} {platform.release()}"
            )
            
            await query.edit_message_text(
                status_message,
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
            
            self.log_action("SYSTEM_STATUS_REQUESTED")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error getting system status: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("SYSTEM_STATUS_ERROR", str(e))
    
    async def prompt_run_command(self, query):
        """Prompt for command to run"""
        await query.edit_message_text(
            "🖥️ **Run Command**\n\n"
            "Please send the command you want to execute.\n"
            "⚠️ Be careful with system commands!",
            parse_mode='Markdown'
        )
        
        # Set context for next message
        query.message.reply_markup = None
    
    async def handle_command_execution(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Execute command sent by user"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            return
        
        command = update.message.text
        
        try:
            # Execute command
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            output = result.stdout if result.stdout else result.stderr
            if not output:
                output = "Command executed successfully (no output)"
            
            # Limit output length
            if len(output) > 4000:
                output = output[:4000] + "...\n[Output truncated]"
            
            await update.message.reply_text(
                f"🖥️ **Command:** `{command}`\n\n"
                f"📄 **Output:**\n```\n{output}\n```",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
            
            self.log_action("COMMAND_EXECUTED", command)
            
        except subprocess.TimeoutExpired:
            await update.message.reply_text(
                f"⏰ Command timed out: `{command}`",
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
            self.log_action("COMMAND_TIMEOUT", command)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error executing command: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("COMMAND_ERROR", f"{command} - {str(e)}")
    
    async def prompt_file_list(self, query):
        """Prompt for directory path"""
        await query.edit_message_text(
            "🧾 **File List**\n\n"
            "Please send the directory path you want to explore.\n"
            "Examples:\n"
            "• `/home/user` (Linux)\n"
            "• `C:\\Users\\User` (Windows)\n"
            "• `.` (current directory)",
            parse_mode='Markdown'
        )
    
    async def handle_file_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List files in directory"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            return
        
        path = update.message.text.strip()
        
        try:
            if not os.path.exists(path):
                await update.message.reply_text(
                    f"❌ Path does not exist: {path}",
                    reply_markup=self.get_main_keyboard()
                )
                return
            
            files = []
            directories = []
            
            for item in os.listdir(path):
                item_path = os.path.join(path, item)
                if os.path.isdir(item_path):
                    directories.append(f"📁 {item}")
                else:
                    size = os.path.getsize(item_path)
                    size_str = self.format_file_size(size)
                    files.append(f"📄 {item} ({size_str})")
            
            # Sort and combine
            all_items = sorted(directories) + sorted(files)
            
            if not all_items:
                file_list = "Empty directory"
            else:
                file_list = "\n".join(all_items[:50])  # Limit to 50 items
                if len(all_items) > 50:
                    file_list += f"\n... and {len(all_items) - 50} more items"
            
            message = f"🧾 **Directory:** `{path}`\n\n{file_list}"
            
            await update.message.reply_text(
                message,
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
            
            self.log_action("FILE_LIST_REQUESTED", path)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error listing files: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("FILE_LIST_ERROR", f"{path} - {str(e)}")
    
    def format_file_size(self, size_bytes):
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        size = size_bytes
        
        while size >= 1024 and i < len(size_names) - 1:
            size /= 1024
            i += 1
        
        return f"{size:.1f} {size_names[i]}"
    
    async def prompt_send_file(self, query):
        """Prompt for file path to send"""
        await query.edit_message_text(
            "📂 **Send File**\n\n"
            "Please send the full path of the file you want to download.\n"
            "⚠️ File size limit: 50MB",
            parse_mode='Markdown'
        )
    
    async def handle_send_file(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send file to user"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            return
        
        file_path = update.message.text.strip()
        
        try:
            if not os.path.exists(file_path):
                await update.message.reply_text(
                    f"❌ File does not exist: {file_path}",
                    reply_markup=self.get_main_keyboard()
                )
                return
            
            if os.path.isdir(file_path):
                await update.message.reply_text(
                    f"❌ Path is a directory, not a file: {file_path}",
                    reply_markup=self.get_main_keyboard()
                )
                return
            
            file_size = os.path.getsize(file_path)
            
            # Check file size (Telegram limit is 50MB)
            if file_size > 50 * 1024 * 1024:
                await update.message.reply_text(
                    f"❌ File too large: {self.format_file_size(file_size)}\n"
                    f"Maximum size: 50MB",
                    reply_markup=self.get_main_keyboard()
                )
                return
            
            # Send file
            with open(file_path, 'rb') as file:
                await update.message.reply_document(
                    document=file,
                    filename=os.path.basename(file_path),
                    caption=f"📂 File: {os.path.basename(file_path)}\n"
                           f"📏 Size: {self.format_file_size(file_size)}",
                    reply_markup=self.get_main_keyboard()
                )
            
            self.log_action("FILE_SENT", file_path)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error sending file: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("SEND_FILE_ERROR", f"{file_path} - {str(e)}")
    
    async def record_audio(self, query):
        """Record audio from microphone"""
        try:
            await query.edit_message_text(f"🔊 Recording audio for {AUDIO_DURATION} seconds...")
            
            # Record audio
            audio_data = sd.rec(
                int(AUDIO_DURATION * AUDIO_SAMPLE_RATE),
                samplerate=AUDIO_SAMPLE_RATE,
                channels=2
            )
            sd.wait()  # Wait until recording is finished
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                import scipy.io.wavfile as wavfile
                wavfile.write(tmp_file.name, AUDIO_SAMPLE_RATE, audio_data)
                tmp_path = tmp_file.name
            
            # Send audio
            with open(tmp_path, 'rb') as audio:
                await query.message.reply_voice(
                    voice=audio,
                    caption=f"🔊 Audio recorded for {AUDIO_DURATION}s at {datetime.now().strftime('%H:%M:%S')}",
                    reply_markup=self.get_main_keyboard()
                )
            
            # Clean up
            os.unlink(tmp_path)
            await query.message.delete()
            
            self.log_action("AUDIO_RECORDED")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error recording audio: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("AUDIO_RECORD_ERROR", str(e))
    
    async def take_webcam_photo(self, query):
        """Take photo with webcam"""
        try:
            await query.edit_message_text("🎥 Taking webcam photo...")
            
            # Initialize camera
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                await query.edit_message_text(
                    "❌ Cannot access webcam",
                    reply_markup=self.get_main_keyboard()
                )
                return
            
            # Take photo
            ret, frame = cap.read()
            cap.release()
            
            if not ret:
                await query.edit_message_text(
                    "❌ Failed to capture image",
                    reply_markup=self.get_main_keyboard()
                )
                return
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_file:
                cv2.imwrite(tmp_file.name, frame)
                tmp_path = tmp_file.name
            
            # Send photo
            with open(tmp_path, 'rb') as photo:
                await query.message.reply_photo(
                    photo=photo,
                    caption=f"🎥 Webcam photo taken at {datetime.now().strftime('%H:%M:%S')}",
                    reply_markup=self.get_main_keyboard()
                )
            
            # Clean up
            os.unlink(tmp_path)
            await query.message.delete()
            
            self.log_action("WEBCAM_PHOTO_TAKEN")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error taking webcam photo: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("WEBCAM_ERROR", str(e))
    
    async def generate_system_report(self, query):
        """Generate comprehensive system report"""
        try:
            await query.edit_message_text("💾 Generating system report...")
            
            # Collect system information
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            boot_time = datetime.fromtimestamp(psutil.boot_time())
            uptime = datetime.now() - boot_time
            
            # Network information
            try:
                network = psutil.net_io_counters()
                network_info = f"📡 **Network:**\n├ Sent: {network.bytes_sent // (1024**2)} MB\n└ Received: {network.bytes_recv // (1024**2)} MB\n\n"
            except:
                network_info = ""
            
            # Process count
            process_count = len(psutil.pids())
            
            # Format uptime
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            uptime_str = f"{days}d {hours}h {minutes}m"
            
            report = (
                f"💾 **System Report**\n"
                f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"🖥️ **System:**\n"
                f"├ OS: {platform.system()} {platform.release()}\n"
                f"├ Node: {platform.node()}\n"
                f"├ Architecture: {platform.architecture()[0]}\n"
                f"└ Python: {platform.python_version()}\n\n"
                f"⚡ **CPU:**\n"
                f"├ Usage: {cpu_percent}%\n"
                f"└ Cores: {cpu_count}\n\n"
                f"💾 **Memory:**\n"
                f"├ Used: {memory.used // (1024**3):.1f} GB ({memory.percent}%)\n"
                f"├ Available: {memory.available // (1024**3):.1f} GB\n"
                f"└ Total: {memory.total // (1024**3):.1f} GB\n\n"
                f"💿 **Disk:**\n"
                f"├ Used: {disk.used // (1024**3):.1f} GB ({disk.used/disk.total*100:.1f}%)\n"
                f"├ Free: {disk.free // (1024**3):.1f} GB\n"
                f"└ Total: {disk.total // (1024**3):.1f} GB\n\n"
                f"{network_info}"
                f"🔧 **System:**\n"
                f"├ Processes: {process_count}\n"
                f"├ Boot time: {boot_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"└ Uptime: {uptime_str}"
            )
            
            await query.edit_message_text(
                report,
                reply_markup=self.get_main_keyboard(),
                parse_mode='Markdown'
            )
            
            self.log_action("SYSTEM_REPORT_GENERATED")
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error generating system report: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("SYSTEM_REPORT_ERROR", str(e))
    
    async def shutdown_pc(self, query):
        """Shutdown PC"""
        try:
            await query.edit_message_text("⏻ Shutting down PC in 10 seconds...")
            
            self.log_action("SHUTDOWN_INITIATED")
            
            # Wait 10 seconds
            await asyncio.sleep(10)
            
            # Execute shutdown command
            if platform.system() == "Windows":
                subprocess.run(["shutdown", "/s", "/t", "0"], check=True)
            else:
                subprocess.run(["shutdown", "-h", "now"], check=True)
                
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error shutting down: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("SHUTDOWN_ERROR", str(e))
    
    async def restart_pc(self, query):
        """Restart PC"""
        try:
            await query.edit_message_text("🔁 Restarting PC in 10 seconds...")
            
            self.log_action("RESTART_INITIATED")
            
            # Wait 10 seconds
            await asyncio.sleep(10)
            
            # Execute restart command  
            if platform.system() == "Windows":
                subprocess.run(["shutdown", "/r", "/t", "0"], check=True)
            else:
                subprocess.run(["reboot"], check=True)
                
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error restarting: {str(e)}",
                reply_markup=self.get_main_keyboard()
            )
            self.log_action("RESTART_ERROR", str(e))
    
    async def send_daily_report(self):
        """Send daily system report"""
        try:
            # Generate report
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            report = (
                f"📊 **Daily System Report**\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"⚡ CPU Usage: {cpu_percent}%\n"
                f"💾 Memory Usage: {memory.percent}%\n"
                f"💿 Disk Usage: {disk.used/disk.total*100:.1f}%\n\n"
                f"System is running normally! 🟢"
            )
            
            await self.send_notification(report)
            self.log_action("DAILY_REPORT_SENT")
            
        except Exception as e:
            self.log_action("DAILY_REPORT_ERROR", str(e))
    
    def schedule_daily_report(self):
        """Schedule daily report"""
        schedule.every().day.at("00:00").do(self.daily_report_job)
    
    def daily_report_job(self):
        """Job wrapper for daily report"""
        if self.app and hasattr(self.app, '_running') and self.app._running:
            # Schedule the coroutine in the main event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.send_daily_report())
    
    def usb_check_job(self):
        """Job wrapper for USB checking"""
        try:
            current_devices = set(self.usb_monitor.get_usb_devices())
            new_devices = current_devices - self.usb_monitor.last_devices
            
            if new_devices and self.app and hasattr(self.app, '_running') and self.app._running:
                message = f"🔌 New USB device(s) detected:\n"
                for device in new_devices:
                    message += f"• {device}\n"
                
                # Schedule the notification in the main event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self.send_notification(message))
            
            self.usb_monitor.last_devices = current_devices
        except Exception as e:
            logger.error(f"Error in USB check: {e}")
    
    def run_schedule(self):
        """Run scheduled tasks in background"""
        while True:
            try:
                schedule.run_pending()
                # Check USB devices every 5 seconds
                self.usb_check_job()
                time.sleep(5)
            except Exception as e:
                logger.error(f"Error in scheduler: {e}")
                time.sleep(5)
    
    (self):
        """Send notification when bot starts"""
        try:
            startup_message = (
                f"🤖 **PC Control Bot Online**\n\n"
                f"🖥️ System: {platform.system()} {platform.release()}\n"
                f"💻 Node: {platform.node()}\n"
                f"⏰ Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"Bot is ready for commands! 🚀"
            )
            
            await self.app.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=startup_message,
                parse_mode='Markdown'
            )
            
            self.log_action("BOT_STARTED")
            
        except Exception as e:
            logger.error(f"Error sending startup notification: {e}")
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages based on context"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            return
        
        text = update.message.text.strip()
        
        # Check if it's a command to execute
        if text and not text.startswith('/'):
            # Check if it looks like a file path
            if os.path.sep in text or text.startswith('.') or text.startswith('~'):
                # Could be file path - check if it's for file list or send file
                if os.path.exists(text):
                    if os.path.isdir(text):
                        await self.handle_file_list(update, context)
                    else:
                        await self.handle_send_file(update, context)
                else:
                    await update.message.reply_text(
                        f"❌ Path does not exist: {text}",
                        reply_markup=self.get_main_keyboard()
                    )
            else:
                # Treat as command to execute
                await self.handle_command_execution(update, context)

# =============================================================================
# CONFIGURATION MANAGER
# =============================================================================

def load_config():
    """Load configuration from file"""
    global BOT_TOKEN, ADMIN_CHAT_ID
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                BOT_TOKEN = config.get('bot_token', BOT_TOKEN)
                ADMIN_CHAT_ID = config.get('admin_chat_id', ADMIN_CHAT_ID)
                logger.info("Configuration loaded from file")
        except Exception as e:
            logger.error(f"Error loading config: {e}")

def save_config():
    """Save configuration to file"""
    config = {
        'bot_token': BOT_TOKEN,
        'admin_chat_id': ADMIN_CHAT_ID
    }
    
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info("Configuration saved to file")
    except Exception as e:
        logger.error(f"Error saving config: {e}")

def setup_config():
    """Interactive configuration setup"""
    global BOT_TOKEN, ADMIN_CHAT_ID
    
    print("=== Telegram PC Control Bot Configuration ===\n")
    
    # Bot Token
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("1. Get your bot token from @BotFather on Telegram")
        print("   - Send /newbot to @BotFather")
        print("   - Choose a name and username for your bot")
        print("   - Copy the token provided")
        token = input("\nEnter your bot token: ").strip()
        if token:
            BOT_TOKEN = token
    
    # Admin Chat ID
    if ADMIN_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("\n2. Get your chat ID:")
        print("   - Send a message to @userinfobot on Telegram")
        print("   - Copy the 'Id' number (it might be negative)")
        chat_id = input("\nEnter your chat ID: ").strip()
        if chat_id:
            ADMIN_CHAT_ID = chat_id
    
    # Save configuration
    save_config()
    print("\n✅ Configuration saved!")

# =============================================================================
# INSTALLATION HELPERS
# =============================================================================

def create_requirements_txt():
    """Create requirements.txt file"""
    requirements = """python-telegram-bot==20.7
psutil==5.9.6
pyautogui==0.9.54
opencv-python==4.8.1.78
sounddevice==0.4.6
numpy==1.24.3
schedule==1.2.0
watchdog==3.0.0
scipy==1.11.4
pywin32==306; sys_platform == "win32"
"""
    
    with open('requirements.txt', 'w') as f:
        f.write(requirements)
    
    print("✅ requirements.txt created!")

def create_startup_scripts():
    """Create startup scripts for different OS"""
    
    # Windows startup script
    windows_bat = """@echo off
cd /d "%~dp0"
python telegram_pc_bot.py
pause
"""
    
    with open('start_bot_windows.bat', 'w') as f:
        f.write(windows_bat)
    
    # Linux startup script
    linux_sh = """#!/bin/bash
cd "$(dirname "$0")"
python3 telegram_pc_bot.py
"""
    
    with open('start_bot_linux.sh', 'w') as f:
        f.write(linux_sh)
    
    # Make Linux script executable
    try:
        os.chmod('start_bot_linux.sh', 0o755)
    except:
        pass
    
    print("✅ Startup scripts created!")
    print("   - Windows: start_bot_windows.bat")
    print("   - Linux: start_bot_linux.sh")

def create_systemd_service():
    """Create systemd service file for Linux"""
    
    current_dir = os.path.abspath(os.path.dirname(__file__))
    python_path = shutil.which('python3') or shutil.which('python')
    
    service_content = f"""[Unit]
Description=Telegram PC Control Bot
After=network.target

[Service]
Type=simple
User=%i
WorkingDirectory={current_dir}
ExecStart={python_path} {os.path.join(current_dir, 'telegram_pc_bot.py')}
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    
    with open('telegram-pc-bot.service', 'w') as f:
        f.write(service_content)
    
    print("✅ Systemd service file created: telegram-pc-bot.service")
    print("\nTo install as system service (Linux):")
    print("1. sudo cp telegram-pc-bot.service /etc/systemd/system/")
    print("2. sudo systemctl daemon-reload")
    print("3. sudo systemctl enable telegram-pc-bot")
    print("4. sudo systemctl start telegram-pc-bot")

def show_installation_guide():
    """Show installation and setup guide"""
    
    print("\n" + "="*60)
    print("🤖 TELEGRAM PC CONTROL BOT - INSTALLATION GUIDE")
    print("="*60)
    
    print("\n📋 STEP 1: Install Dependencies")
    print("   pip install -r requirements.txt")
    
    print("\n🔧 STEP 2: Configuration")
    print("   Run the bot with --setup flag to configure:")
    print("   python telegram_pc_bot.py --setup")
    
    print("\n🚀 STEP 3: Auto-start Setup")
    print("\n   📱 Windows:")
    print("   1. Press Win+R, type 'shell:startup'")
    print("   2. Copy 'start_bot_windows.bat' to the startup folder")
    print("   3. Or create a scheduled task in Task Scheduler")
    
    print("\n   🐧 Linux (systemd):")
    print("   1. sudo cp telegram-pc-bot.service /etc/systemd/system/")
    print("   2. sudo systemctl daemon-reload")
    print("   3. sudo systemctl enable telegram-pc-bot")
    print("   4. sudo systemctl start telegram-pc-bot")
    
    print("\n   🐧 Linux (crontab):")
    print("   1. crontab -e")
    print("   2. Add: @reboot /path/to/start_bot_linux.sh")
    
    print("\n🔒 STEP 4: Security Notes")
    print("   - Keep your bot token secure")
    print("   - Only share your chat ID with trusted users")
    print("   - Run the bot with appropriate user permissions")
    
    print("\n✅ STEP 5: Usage")
    print("   1. Start the bot: python telegram_pc_bot.py")
    print("   2. Send /start to your bot on Telegram")
    print("   3. Use the interactive buttons to control your PC")
    
    print("\n" + "="*60)

# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    """Main function"""
    
    # Check command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == '--setup':
            setup_config()
            return
        elif sys.argv[1] == '--install':
            create_requirements_txt()
            create_startup_scripts()
            create_systemd_service()
            show_installation_guide()
            return
        elif sys.argv[1] == '--help':
            show_installation_guide()
            return
    
    # Load configuration
    load_config()
    
    # Check if configuration is needed
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or ADMIN_CHAT_ID == "YOUR_CHAT_ID_HERE":
        print("⚠️  Configuration required!")
        print("Run with --setup flag to configure the bot:")
        print("python telegram_pc_bot.py --setup")
        return
    
    # Create and run bot
    bot = PCControlBot()
    
    try:
        # Run the bot
        asyncio.run(bot.run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Clean up
        try:
            if hasattr(bot, 'observer') and bot.observer and bot.observer.is_alive():
                bot.observer.stop()
                bot.observer.join()
        except:
            pass

if __name__ == "__main__":
    main(
    async def run_bot(self):
        """Main bot runner"""
        try:
            # Validate configuration
            if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or ADMIN_CHAT_ID == "YOUR_CHAT_ID_HERE":
                logger.error("Please configure BOT_TOKEN and ADMIN_CHAT_ID in the script!")
                return

            # Create application
            self.app = Application.builder().token(BOT_TOKEN).build()

            # Add handlers
            self.app.add_handler(CommandHandler("start", self.start_command))
            self.app.add_handler(CallbackQueryHandler(self.button_callback))
            self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))

            # Send startup notification and start background schedule
            await self.send_startup_notification()

            self.schedule_daily_report()
            schedule_thread = threading.Thread(target=self.run_schedule, daemon=True)
            schedule_thread.start()

            logger.info("Bot started successfully!")

            # Run the bot
            await self.app.run_polling(drop_pending_updates=True)

        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise


)