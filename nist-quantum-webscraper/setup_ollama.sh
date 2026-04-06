#!/bin/bash

# Setup script for Ollama and AI dependencies

echo "🚀 Setting up Ollama for AI Summaries"
echo "======================================"

# Check if Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "📦 Ollama not found. Installing Ollama..."
    
    # Check platform and install accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "🍎 Detected macOS"
        if command -v brew &> /dev/null; then
            brew install ollama
        else
            echo "❌ Homebrew not found. Please install Homebrew first:"
            echo "   https://brew.sh/"
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "🐧 Detected Linux"
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "❓ Unsupported platform. Please install Ollama manually:"
        echo "   https://ollama.com/download"
        exit 1
    fi
else
    echo "✅ Ollama is already installed"
fi

# Start Ollama service
echo "🔧 Starting Ollama service..."
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if command -v brew &> /dev/null; then
        brew services start ollama
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    sudo systemctl start ollama
    sudo systemctl enable ollama
fi

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to be ready..."
sleep 5

# Install the Llama2 model (good balance of performance and resource usage)
echo "📥 Installing Llama2 model..."
ollama pull llama2

# Verify installation
echo "🔍 Verifying installation..."
ollama list

echo ""
echo "✅ Ollama setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Run the test script: python test_ai_summaries.py"
echo "2. Start the dashboard: streamlit run src/dashboard/app.py"
echo "3. AI summaries will be generated automatically when you open item expanders"
echo ""
echo "💡 Tips:"
echo "- If you want better performance, you can install larger models:"
echo "  ollama pull llama2:13b"
echo "  ollama pull codellama"
echo "- Models are cached locally, so subsequent runs will be faster"
echo "- Summaries are cached to avoid regenerating them"