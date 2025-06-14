# 🤖 Telegram PC Control Bot - Installation Guide

A comprehensive Telegram bot for remote PC control with interactive buttons, compatible with Windows and Linux systems.

## 📋 Features

- **Interactive Button Interface**: No need to remember commands - just click buttons!
- **Screenshot & Webcam**: Take screenshots and webcam photos remotely
- **System Monitoring**: CPU, RAM, disk usage, and real-time status
- **File Management**: Browse directories, send/receive files
- **Audio Recording**: Record microphone audio remotely  
- **Command Execution**: Run system commands safely
- **USB Monitoring**: Get notified when USB devices are connected
- **Scheduled Reports**: Daily system reports at midnight
- **Auto-start**: Automatically starts when PC boots
- **Comprehensive Logging**: All actions logged with timestamps

## 🚀 Quick Start

### Step 1: Get Bot Token and Chat ID

#### Getting Bot Token:
1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Choose a name for your bot (e.g., "My PC Control Bot")
4. Choose a username (e.g., "my_pc_control_bot")
5. Copy the token provided (looks like: `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`)

#### Getting Your Chat ID:
1. Send a message to `@userinfobot` on Telegram
2. Copy the `Id` number (it might be negative, like `-1234567890`)

### Step 2: Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# For Linux, you might need additional packages:
sudo apt-get install python3-pyaudio portaudio19-dev  # Ubuntu/Debian
# or
sudo yum install python3-pyaudio portaudio-devel     # CentOS/RHEL
```

### Step 3: Configure the Bot

```bash
# Run setup wizard
python telegram_pc_bot.py --setup
```

This will prompt you to enter:
- Your bot token
- Your chat ID

Configuration is saved in `bot_config.json`.

### Step 4: Test the Bot

```bash
# Start the bot
python telegram_pc_bot.py
```

Send `/start` to your bot on Telegram to test it works!

## 🔧 Auto-start Configuration

### Windows

#### Method 1: Startup Folder (Simple)
1. Press `Win + R`, type `shell:startup`, press Enter
2. Copy the `start_bot_windows.bat` file to this folder
3. The bot will start automatically when you log in

#### Method 2: Task Scheduler (Advanced)
1. Open Task Scheduler (`taskschd.msc`)
2. Create Basic Task
3. Name: "Telegram PC Bot"
4. Trigger: "When the computer starts"
5. Action: "Start a program"
6. Program: `python`
7. Arguments: `C:\path\to\telegram_pc_bot.py`
8. Start in: `C:\path\to\bot\directory`

### Linux

#### Method 1: Systemd Service (Recommended)
```bash
# Install as system service
python telegram_pc_bot.py --install

# Copy service file
sudo cp telegram-pc-bot.service /etc/systemd/system/

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable telegram-pc-bot
sudo systemctl start telegram-pc-bot

# Check status
sudo systemctl status telegram-pc-bot

# View logs
sudo journalctl -u telegram-pc-bot -f
```

#### Method 2: Crontab
```bash
# Edit crontab
crontab -e

# Add this line (replace with your actual path):
@reboot /home/user/telegram-bot/start_bot_linux.sh
```

#### Method 3: Desktop Autostart
```bash
# Create autostart entry
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/telegram-pc-bot.desktop << EOF
[Desktop Entry]
Type=Application
Name=Telegram PC Bot
Exec=/path/to/start_bot_linux.sh
Hidden=false
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF
```

## 🎮 Using the Bot

### Available Commands

Send `/start` to your bot to see the interactive menu with these options:

- 📸 **Screenshot**: Capture and send desktop screenshot
- 🧠 **System Status**: Get CPU, RAM, disk usage
- 🖥️ **Run Command**: Execute system commands
- 🧾 **File List**: Browse directory contents
- 📂 **Send File**: Download files from PC
- 🔊 **Record Audio**: Record microphone (10 seconds)
- 🎥 **Webcam**: Take webcam photo
- 💾 **System Report**: Comprehensive system information
- ⏻ **Shutdown**: Safely shutdown PC
- 🔁 **Restart**: Restart PC

### Example Usage

1. **Taking a Screenshot**:
   - Click "📸 Screenshot" button
   - Bot captures and sends current screen

2. **Running Commands**:
   - Click "🖥️ Run Command" button
   - Send command like `dir` (Windows) or `ls -la` (Linux)
   - Bot executes and returns output

3. **File Management**:
   - Click "🧾 File List" → Send path like `C:\Users` or `/home/user`
   - Click "📂 Send File" → Send full file path to download

## 🔒 Security Features

- **Admin-Only Access**: Only responds to configured admin chat ID
- **Command Logging**: All actions logged with timestamps
- **Safe Execution**: Commands run with user permissions only
- **File Size Limits**: 50MB limit for file transfers
- **Timeout Protection**: Commands timeout after 30 seconds

## 📝 Configuration Files

### bot_config.json
```json
{
  "bot_token": "your_bot_token_here",
  "admin_chat_id": "your_chat_id_here"
}
```

### Log Files
- `bot_log.txt`: Contains all bot actions and errors
- Logs include timestamps, actions, and details
- Automatically rotated to prevent excessive size

## 🐛 Troubleshooting

### Common Issues

#### "ModuleNotFoundError"
```bash
# Install missing dependencies
pip install -r requirements.txt
```

#### "Cannot access webcam"
- Check if camera is not used by another application
- On Linux, user might need to be in `video` group:
```bash
sudo usermod -a -G video $USER
```

#### "Permission denied" for shutdown/restart
- On Linux, you might need to allow shutdown without password:
```bash
# Add to sudoers file:
echo "$USER ALL=(ALL) NOPASSWD: /sbin/shutdown, /sbin/reboot" | sudo tee /etc/sudoers.d/telegram-bot
```

#### Bot not responding
1. Check if bot token is correct
2. Verify chat ID is correct (include negative sign if present)
3. Check internet connection
4. Look at logs in `bot_log.txt`

#### Audio recording issues
```bash
# Linux - install audio dependencies
sudo apt-get install python3-pyaudio portaudio19-dev

# Test audio devices
python -c "import sounddevice as sd; print(sd.query_devices())"
```

### Checking Bot Status

#### Linux (systemd)
```bash
# Check if service is running
sudo systemctl status telegram-pc-bot

# View recent logs
sudo journalctl -u telegram-pc-bot -n 50

# Restart service
sudo systemctl restart telegram-pc-bot
```

#### Manual Check
```bash
# Check if bot process is running
ps aux | grep telegram_pc_bot

# Check log file
tail -f bot_log.txt
```

## 🔧 Advanced Configuration

### Customizing Audio Recording
Edit these variables in the script:
```python
AUDIO_DURATION = 10  # seconds
AUDIO_SAMPLE_RATE = 44100
```

### Changing Daily Report Time
```python
# In schedule_daily_report() function
schedule.every().day.at("00:00").do(...)  # Change time here
```

### USB Monitoring Paths (Linux)
```python
# In USBMonitor class, modify mount points:
for mount_point in ['/media', '/mnt', '/run/media']:
```

## 📚 API Reference

### Main Commands
- `/start` - Show main menu with interactive buttons

### Button Callbacks
All interactions use inline keyboard buttons instead of text commands for better user experience.

## 🤝 Contributing

Feel free to submit issues and enhancement requests!

## 📄 License

This project is provided as-is for educational and personal use.

## ⚠️ Disclaimer

This bot provides powerful remote access to your computer. Use responsibly and ensure your bot token and chat ID are kept secure. The authors are not responsible for any misuse or damage caused by this software.

---

**Happy Remote Computing! 🚀**