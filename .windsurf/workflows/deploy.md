---
description: Deploy AI Agent to cloud for 24/7 operation
---

# Deploy AI Agent to Cloud (24/7 Operation)

## Recommended: PythonAnywhere (Free Tier)

### Step 1: Sign Up
1. Go to [pythonanywhere.com](https://www.pythonanywhere.com)
2. Create free account
3. Confirm email

### Step 2: Upload Files
```bash
# In PythonAnywhere console:
# 1. Go to Files tab
# 2. Upload all your ai_agent folder files
# OR use git:
git clone https://github.com/yourusername/ai-agent.git
```

### Step 3: Setup Environment
```bash
# Open Bash console in PythonAnywhere
mkvirtualenv ai-agent --python=python3.11
workon ai-agent

# Install dependencies
pip install -r requirements.txt
```

### Step 4: Configure .env
```bash
# Edit .env file in Files tab or via console
nano ai_agent/.env

# Add your credentials:
WHATSAPP_DIRECT_PHONE=+919381265797
EMAIL_ENABLED=true
EMAIL_SENDER=grdevelopers.co@gmail.com
EMAIL_PASSWORD=your_app_password
EMAIL_RECIPIENT=gnanarajeswarareddy1607@gmail.com
NEWS_API_KEY=your_key
```

### Step 5: Create Scheduled Task
```bash
# Go to Tasks tab in PythonAnywhere
# Add new scheduled task:
cd ~/ai_agent && python main.py

# Set schedule: Daily at 00:25 UTC (6:00 AM IST)
```

### Step 6: Keep Alive (Optional)
```bash
# For continuous ingestion, use:
cd ~/ai_agent && nohup python main.py > agent.log 2>&1 &
```

---

## Alternative: Railway.app (Free Tier)

### Step 1: Sign Up
1. Go to [railway.app](https://railway.app)
2. Login with GitHub
3. New Project → Deploy from GitHub repo

### Step 2: Add Procfile
Create `Procfile` in your repo:
```
worker: python ai_agent/main.py
```

### Step 3: Environment Variables
In Railway dashboard → Variables:
- Add all .env variables

### Step 4: Deploy
Railway auto-deploys on git push.

---

## Alternative: AWS EC2 (Free 12 months)

### Step 1: Launch Instance
1. AWS Console → EC2 → Launch Instance
2. Amazon Linux 2023 (t2.micro - free tier)
3. Create/download key pair

### Step 2: Connect & Setup
```bash
ssh -i your-key.pem ec2-user@your-ec2-ip

sudo yum update -y
sudo yum install python3 python3-pip git -y

# Clone repo
git clone https://github.com/yourusername/ai-agent.git
cd ai-agent

# Install dependencies
pip3 install -r requirements.txt

# Create service for auto-start
sudo nano /etc/systemd/system/ai-agent.service
```

### Step 3: Create Systemd Service
```ini
[Unit]
Description=AI Agent Service
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/ai-agent/ai_agent
ExecStart=/usr/bin/python3 /home/ec2-user/ai-agent/ai_agent/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### Step 4: Start Service
```bash
sudo systemctl enable ai-agent
sudo systemctl start ai-agent
sudo systemctl status ai-agent
```

---

## Monitoring & Logs

### PythonAnywhere Logs:
- Go to Tasks tab → View logs

### AWS Logs:
```bash
sudo journalctl -u ai-agent -f
```

### Railway Logs:
- Dashboard → Deployments → Logs

---

## Important Notes

1. **WhatsApp Web**: Still requires QR code scan initially
   - Use PythonAnywhere + VNC or connect once locally, copy session

2. **Email**: Works immediately on all platforms

3. **Database**: SQLite persists on all options

4. **Scheduler**: 
   - PythonAnywhere: Built-in scheduler
   - Railway: Use APScheduler (already in code)
   - AWS: Systemd timer or cron

---

## Quick Deploy (Copy-Paste)

For PythonAnywhere (Easiest):
```bash
# 1. Upload files via Files tab
# 2. Open Bash console:
cd ~
python3 -m venv venv
source venv/bin/activate
pip install -r ai_agent/requirements.txt

# 3. Set environment variables in .env
# 4. Go to Tasks, add: cd ~/ai_agent && python main.py
# 5. Set time: 00:25 daily (6:00 AM IST)
```
