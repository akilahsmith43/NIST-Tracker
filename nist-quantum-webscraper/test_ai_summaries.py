#!/usr/bin/env python3
"""
Test script for AI summaries implementation.
This script tests the AI summary generation system.
"""

import sys
import os
import logging
from datetime import datetime

# Add the src directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all required modules can be imported."""
    try:
        from src.utils.content_fetcher import ContentFetcher
        from src.utils.ai_summarizer import AISummarizer
        from src.utils.summary_manager import SummaryManager
        from src.data.data_storage import DataStorage
        logger.info("✅ All modules imported successfully")
        return True
    except ImportError as e:
        logger.error(f"❌ Import error: {e}")
        return False

def test_content_fetcher():
    """Test content fetching functionality."""
    try:
        from src.utils.content_fetcher import ContentFetcher
        fetcher = ContentFetcher()
        
        # Test with a simple NIST URL
        test_url = "https://www.nist.gov/publications/robust-phase-stabilization-dark-quantum-channel-over-120-km-deployed-fiber-link"
        content = fetcher.fetch_content(test_url)
        
        if content.get('error'):
            logger.warning(f"⚠️ Content fetching warning: {content['error']}")
            return False
        
        if content.get('body') or content.get('abstract'):
            logger.info("✅ Content fetching works")
            return True
        else:
            logger.warning("⚠️ No content extracted")
            return False
            
    except Exception as e:
        logger.error(f"❌ Content fetcher test failed: {e}")
        return False

def test_ai_summarizer():
    """Test AI summarization functionality."""
    try:
        from src.utils.ai_summarizer import AISummarizer
        
        # Test with sample content
        sample_content = """
        This is a test publication about quantum computing. 
        It discusses the latest advancements in quantum algorithms and their applications.
        The research shows significant improvements in computational efficiency.
        """
        
        summarizer = AISummarizer()
        
        # Test connection
        if not summarizer.test_connection():
            logger.warning("⚠️ Ollama connection test failed - this is expected if Ollama is not running")
            return False
        
        # Test summarization
        summary = summarizer.generate_summary(sample_content)
        
        if summary and summary != "Summary generation failed.":
            logger.info(f"✅ AI summarization works: {summary[:50]}...")
            return True
        else:
            logger.warning("⚠️ AI summarization failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ AI summarizer test failed: {e}")
        return False

def test_summary_manager():
    """Test summary manager functionality."""
    try:
        from src.utils.summary_manager import SummaryManager
        
        manager = SummaryManager()
        
        # Test that the manager can be instantiated
        logger.info("✅ Summary manager instantiated successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Summary manager test failed: {e}")
        return False

def test_data_storage():
    """Test data storage functionality."""
    try:
        from src.data.data_storage import DataStorage
        
        storage = DataStorage()
        
        # Test item identity generation
        test_item = {
            'document_name': 'Test Publication',
            'link': 'https://example.com/test',
            'release_date': 'March 1, 2025'
        }
        
        identity = storage._build_item_identity(test_item)
        if identity:
            logger.info(f"✅ Data storage works, identity: {identity}")
            return True
        else:
            logger.warning("⚠️ Data storage identity generation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Data storage test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing AI Summaries Implementation")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("Content Fetcher Test", test_content_fetcher),
        ("AI Summarizer Test", test_ai_summarizer),
        ("Summary Manager Test", test_summary_manager),
        ("Data Storage Test", test_data_storage),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Running {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
    
    print("\n" + "=" * 50)
    print("📊 Test Results Summary:")
    print("=" * 50)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Overall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! AI summaries implementation is ready.")
    else:
        print("⚠️ Some tests failed. Check the logs above for details.")
        print("\n💡 Note: AI summarization tests may fail if Ollama is not installed or running.")
        print("   Install Ollama from: https://ollama.com/")
        print("   Then run: ollama pull llama2")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)