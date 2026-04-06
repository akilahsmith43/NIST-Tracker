# AI Summaries with DSPy and Ollama

This implementation adds AI-generated summaries to the NIST Quantum Tracker dashboard using DSPy running on Ollama. The summaries are concise (2 sentences maximum) and generated from the actual content of each item's webpage.

## Features

- **AI-Generated Summaries**: 2-sentence summaries for all publications, presentations, and news items
- **Content Fetching**: Automatically fetches content from item URLs for accurate summarization
- **Smart Caching**: Summaries are cached to avoid regeneration and improve performance
- **Cross-Platform**: Works on all three topic pages (Quantum Information Science, Post-Quantum Cryptography, Artificial Intelligence)
- **Error Resilience**: Graceful fallbacks when content fetching or AI generation fails

## Architecture

### Core Components

1. **ContentFetcher** (`src/utils/content_fetcher.py`)
   - Fetches content from NIST and other URLs
   - Extracts clean text using multiple strategies
   - Implements intelligent caching
   - Handles different website structures

2. **AISummarizer** (`src/utils/ai_summarizer.py`)
   - Uses DSPy with Ollama backend
   - Generates exactly 2-sentence summaries
   - Implements prompt engineering for technical content
   - Includes fallback mechanisms

3. **SummaryManager** (`src/utils/summary_manager.py`)
   - Orchestrates content fetching and summarization
   - Manages caching and storage
   - Determines when to generate summaries
   - Provides easy integration interface

4. **Enhanced DataStorage** (`src/data/data_storage.py`)
   - Stores AI summaries persistently
   - Manages summary caching
   - Integrates with existing data storage

## Installation

### 1. Install Dependencies

```bash
cd nist-quantum-webscraper
pip install -r requirements.txt
```

### 2. Set up Ollama

Run the setup script to install and configure Ollama:

```bash
./setup_ollama.sh
```

Or manually:

1. **Install Ollama**:
   - **macOS**: `brew install ollama`
   - **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`
   - **Windows**: Download from [ollama.com](https://ollama.com/download)

2. **Start Ollama Service**:
   ```bash
   # macOS
   brew services start ollama
   
   # Linux
   sudo systemctl start ollama
   sudo systemctl enable ollama
   ```

3. **Install Model**:
   ```bash
   ollama pull llama2
   ```

### 3. Test Installation

```bash
python test_ai_summaries.py
```

## Usage

### Dashboard Integration

The AI summaries are automatically integrated into the existing dashboard:

1. **Start the Dashboard**:
   ```bash
   streamlit run src/dashboard/app.py
   ```

2. **Navigate to any topic page**:
   - Quantum Information Science
   - Post-Quantum Cryptography
   - Artificial Intelligence

3. **Open any item expander**:
   - Publications
   - Presentations
   - News items

4. **View AI Summary**:
   - Summaries appear prominently in the expander
   - Generated on-demand when first opened
   - Cached for subsequent views

### Summary Generation Process

1. **User opens item expander**
2. **System checks cache** for existing summary
3. **If no cache exists**:
   - Fetch content from item URL
   - Extract clean text content
   - Generate 2-sentence AI summary using DSPy/Ollama
   - Cache the summary for future use
4. **Display summary** in the expander

## Configuration

### Model Selection

Edit `src/utils/ai_summarizer.py` to use different models:

```python
# Change the model name in the constructor
self.ollama_model = dspy.OllamaLocal(model="llama2:13b")  # Larger model
# or
self.ollama_model = dspy.OllamaLocal(model="codellama")   # Code-focused
```

### Summary Length

The system enforces exactly 2 sentences through validation. To modify:

```python
# In ai_summarizer.py, modify _validate_summary_length()
def _validate_summary_length(self, summary: str) -> bool:
    sentences = summary.count('.') + summary.count('!') + summary.count('?')
    return 1 <= sentences <= 3  # Allow 1-3 sentences
```

### Caching

- **Content Cache**: 24 hours (configurable)
- **Summary Cache**: Persistent (until manually cleared)
- **Cache Location**: `data_storage/cache/` and `data_storage/summaries/`

## Performance

### Optimization Features

1. **Content Caching**: Fetched content is cached for 24 hours
2. **Summary Caching**: Generated summaries are stored permanently
3. **Lazy Loading**: Summaries generated only when expanders are opened
4. **Rate Limiting**: Prevents overwhelming Ollama with requests
5. **Error Handling**: Graceful degradation when AI generation fails

### Resource Usage

- **Memory**: ~100MB for DSPy + Ollama model
- **Storage**: ~10MB for cached content and summaries
- **Network**: Minimal (only when fetching new content)

## Troubleshooting

### Common Issues

1. **Ollama Not Found**:
   ```bash
   # Check if Ollama is running
   ollama list
   
   # If not running, start it
   ollama serve
   ```

2. **Model Not Available**:
   ```bash
   # Check available models
   ollama list
   
   # Pull the required model
   ollama pull llama2
   ```

3. **Content Fetching Failed**:
   - Check internet connection
   - Verify URL accessibility
   - Check for website blocking

4. **Summary Generation Failed**:
   - Verify Ollama is running
   - Check model availability
   - Review logs for specific errors

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Manual Testing

Test individual components:

```python
from utils.content_fetcher import ContentFetcher
from utils.ai_summarizer import AISummarizer

# Test content fetching
fetcher = ContentFetcher()
content = fetcher.fetch_content("https://example.com")

# Test AI summarization
summarizer = AISummarizer()
summary = summarizer.generate_summary("Your content here")
```

## Development

### Adding New Models

1. Install the model in Ollama:
   ```bash
   ollama pull your-model-name
   ```

2. Update the model name in `AISummarizer`:
   ```python
   self.ollama_model = dspy.OllamaLocal(model="your-model-name")
   ```

### Customizing Prompts

Modify the prompt template in `AISummarizer._generate_prompt()`:

```python
prompt = f"""Please generate a concise 2-sentence summary of the following content. 
Focus on the key findings, main points, and significance of the work. 
The summary should be exactly 2 sentences long and capture the essence of the content.

Content:
{content}

Summary (exactly 2 sentences):"""
```

### Extending to Other Item Types

The system can be extended to other item types by:

1. Adding the item type to the dashboard integration
2. Ensuring the item has a valid URL
3. Testing content extraction for the new source

## Security

- **Content Fetching**: Uses HTTPS and validates SSL certificates
- **AI Processing**: Runs locally, no data sent to external services
- **Caching**: Local storage only, no cloud dependencies
- **Input Validation**: Sanitizes all URLs and content

## Contributing

1. Fork the repository
2. Create a feature branch
3. Test thoroughly with the test suite
4. Submit a pull request

## License

This feature is part of the NIST Quantum Tracker project. See the main LICENSE file for details.

## Support

For issues related to AI summaries:

1. Check the troubleshooting section
2. Run the test suite: `python test_ai_summaries.py`
3. Review logs for specific error messages
4. Create an issue with detailed error information

For general project support, see the main project README.