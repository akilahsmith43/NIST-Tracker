# NIST Quantum Tracker - Running Instructions

## How to Run the Application

### 1. **Prerequisites**
- Download Python 3.8 or higher on operating system & Extension on vscode
- pip (Python package installer)

### 2. **Setup Instructions**

#### Option A: Using the Virtual Environment (Recommended)
```bash
# Navigate to the project directory
cd /Users/akilahsmith/NIST-Tracker

# Activate the virtual environment
source .venv/bin/activate

# Install dependencies (if not already installed)
pip install -r nist-quantum-webscraper/requirements.txt

# Run the application
streamlit run nist-quantum-webscraper/src/dashboard/app.py
```

#### Option B: Using System Python
```bash
# Navigate to the project directory
cd /Users/akilahsmith/NIST-Tracker

# Install dependencies
pip install -r nist-quantum-webscraper/requirements.txt

# Run the application
streamlit run nist-quantum-webscraper/src/dashboard/app.py
```

### Windows Setup

**Create the virtual environment:**
```powershell
python -m venv .venv
```

**If you get an execution policy error, run this in PowerShell first:**
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

**Then activate the virtual environment:**
```powershell
.\.venv\Scripts\Activate.ps1
```

**Install dependencies:**
```powershell
pip install -r nist-quantum-webscraper/requirements.txt
```

> Note: The Set-ExecutionPolicy command must be re-run each new PowerShell session. It does not permanently change system settings.
### 3. **What You'll See**

#### Terminal Output:
```
You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.1.100:8501

  For better performance, install the Watchdog module:

  $ xcode-select --install
  $ pip install watchdog
```

#### Web Browser:
- Open your web browser
- Navigate to the Local URL shown in the terminal (e.g., http://localhost:8501)
- You'll see the NIST Quantum Tracker dashboard

### 4. **About Localhost Ports**

**Will you have a different localhost every time?**
- **No, usually the same port**: Streamlit typically uses port 8501 by default
- **If port is busy**: Streamlit will automatically try the next available port (8502, 8503, etc.)
- **Consistent experience**: Once you know your port, it will usually stay the same unless something else is using it

### 5. **How to Stop the Application**
- In the terminal where Streamlit is running, press `Ctrl + C`
- Or close the terminal window

### 6. **How to Restart**
- Simply run the same command again:
  ```bash
  streamlit run nist-quantum-webscraper/src/dashboard/app.py
  ```

### 7. **Notification System**

The application will:
- **First run**: Show all current data (no notifications since nothing was saved before)
- **Subsequent runs**: Compare with saved data and show notifications for new items
- **Data persistence**: Your notification history is saved in the `data_storage/` folder

### 8. **Troubleshooting**

#### If you see import errors:
```bash
# Make sure you're in the right directory
cd /Users/akilahsmith/NIST-Tracker

# Activate virtual environment if using it
source .venv/bin/activate

# Reinstall dependencies
pip install -r nist-quantum-webscraper/requirements.txt
```

#### If Streamlit isn't installed:
```bash
pip install streamlit
```

#### If you get port conflicts:
- Streamlit will automatically suggest an alternative port
- Just use the new URL it provides

### 9. **Daily Usage**

1. **Open terminal**
2. **Navigate to project**: `cd /Users/akilahsmith/NIST-Tracker`
3. **Activate virtual environment**: `source .venv/bin/activate` (if using it)
4. **Run the app**: `streamlit run nist-quantum-webscraper/src/dashboard/app.py`
5. **Open browser** to the provided localhost URL
6. **Check the sidebar** for notifications of new content
7. **Refresh the page** to check for new updates

### 10. **What the Notifications Track**

The system will notify you when:
- New publications are added to NIST CSRC
- New presentations are posted
- New quantum-related news is published
- New drafts are opened for comment

The notifications are smart - they only show genuinely new content since your last visit!