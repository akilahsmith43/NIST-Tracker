# NIST Quantum Web Scraper

This project is a web scraper designed to collect information related to quantum information science from various NIST websites. The scraper gathers data on publications, presentations, and news articles, organizing the information into structured formats for easy access and analysis.

## Project Structure

```
nist-quantum-webscraper
├── .DS_Store
├── AI_SUMMARIES_README.md
├── README.md
├── requirements.txt
├── setup_ollama.sh
├── test_ai_summaries.py
├── test_urls.py
├── data_storage/
│   ├── cache/
│   └── dashboard/
│       └── data_storage/
├── src/
│   ├── config/
│   ├── dashboard/
│   │   ├── app.py
│   │   └── data_storage/
│   ├── data/
│   │   ├── data_processing.py
│   │   └── data_storage.py
│   ├── data_storage/
│   │   └── summaries/
│   ├── scraper/
│   │   ├── ai_scraper.py
│   │   ├── pqc_scraper.py
│   │   ├── qis_scraper.py
│   │   └── publications_scraper.py
│   └── utils/
│       ├── ai_summarizer.py
│       ├── backfill_publication_summaries.py
│       ├── clear_cache.py
│       ├── content_fetcher.py
│       ├── helpers.py
│       ├── summary_manager.py
│       └── validate_summaries.py
├── .gitignore
└── debug_pub.py
```

## Installation

To set up the project, follow these steps:

1. Clone the repository:
   ```
   git clone <repository-url>
   cd nist-quantum-webscraper
   ```

2. Install the required packages:
   ```
   pip install -r requirements.txt
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
pip install -r requirements.txt
```

> Note: The Set-ExecutionPolicy command must be re-run each new PowerShell session. It does not permanently change system settings.

## Usage

1. Run the individual scrapers to collect data:
   - For publications:
     ```
     python src/scraper/publications_scraper.py
     ```
   - For presentations:
     ```
     python src/scraper/presentations_scraper.py
     ```
   - For news:
     ```
     python src/scraper/news_scraper.py
     ```

2. Process the scraped data:
   ```
   python src/data/data_processing.py
   ```

3. Launch the dashboard:
   ```
   streamlit run src/dashboard/app.py
   ```

## Goals

The primary goal of this project is to facilitate access to NIST's quantum information science resources by providing a user-friendly dashboard that displays organized data on publications, presentations, and news articles.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any suggestions or improvements.
