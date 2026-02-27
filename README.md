# NIST Quantum Web Scraper

This project is a web scraper designed to collect information related to quantum information science from various NIST websites. The scraper gathers data on publications, presentations, and news articles, organizing the information into structured formats for easy access and analysis.

## Project Structure

```
nist-quantum-webscraper
├── src
│   ├── scraper
│   │   ├── publications_scraper.py  # Scrapes publication data
│   │   ├── presentations_scraper.py  # Scrapes presentation data
│   │   └── news_scraper.py           # Scrapes news articles
│   ├── data
│   │   └── data_processing.py         # Handles data comparison and storage
│   ├── dashboard
│   │   └── app.py                     # Main entry point for the dashboard
│   └── utils
│       └── helpers.py                 # Utility functions for common tasks
├── requirements.txt                    # Lists necessary Python packages
└── README.md                           # Project documentation
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
