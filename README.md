# Nepali Document OCR with Gemini API

A production-ready, industrial-strength OCR system for processing scanned Nepali documents using Google's Gemini AI models. Features intelligent API key rotation, rate limit management, and comprehensive error handling optimized for free tier usage.

## 📋 Features

### 🎯 Core Features
- **High Accuracy OCR**: Optimized for Nepali/Devanagari script with specialized preprocessing
- **Multiple API Key Rotation**: Intelligent rotation strategies to maximize free tier limits
- **Rate Limit Management**: Respects Gemini free tier limits (5 RPM, 20 RPD per key)
- **Batch Processing**: Efficient processing of large document collections
- **Automatic Retries**: Robust error handling with exponential backoff
- **Comprehensive Logging**: Detailed logs for monitoring and debugging

### 🔄 Advanced Features
- **Smart Scheduling**: Process during off-peak hours to avoid rate limits
- **Image Preprocessing**: Automatic enhancement for better OCR accuracy
- **Metadata Preservation**: Complete processing history and statistics
- **Graceful Degradation**: Continue processing despite individual failures
- **Docker Support**: Containerized deployment ready

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- Gemini API keys (free tier supports multiple keys)
- Basic understanding of Python environments

### Installation

1. **Clone and setup**
```bash
git clone <repository-url>
cd nepali-ocr-doc
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure API keys**

Create `api_keys.json`:
```json
[
  {"key": "your_gemini_api_key_1", "alias": "key1"},
  {"key": "your_gemini_api_key_2", "alias": "key2"},
  {"key": "your_gemini_api_key_3", "alias": "key3"},
  {"key": "your_gemini_api_key_4", "alias": "key4"}
]
```

Or use environment variables:
```bash
export GEMINI_API_KEY_1="your_key_1"
export GEMINI_API_KEY_2="your_key_2"
```

### Quick Run
```bash
# Create required directories
mkdir -p images annotations

# Place your Nepali document images in images/ folder

# Run OCR processor
python main.py
```

## 📁 Project Structure

```
nepali-ocr-doc/
├── config/
│   └── settings.py           # Configuration settings
├── src/
│   ├── api_key_manager.py    # API key rotation management
│   ├── rate_limiter.py       # Rate limiting implementation
│   ├── ocr_processor.py      # Gemini OCR processing
│   ├── image_preprocessor.py # Image enhancement
│   └── utils.py              # Utility functions
├── images/                   # Input images (user created)
├── annotations/              # Output annotations (generated)
├── api_keys.json            # API key configuration
├── requirements.txt          # Python dependencies
├── main.py                  # Main processing script
└── anage_keys.py           # Key management utility
```

## ⚙️ Configuration

### Key Configuration Options

Edit `config/settings.py` to customize:

```python
# API Settings
GEMINI_MODEL = "gemini-2.5-flash"  # Model to use
REQUESTS_PER_MINUTE = 5           # Free tier: 5 requests/minute
REQUESTS_PER_DAY = 20             # Free tier: 20 requests/day/key per API Key

# Processing Settings
REQUEST_DELAY_SECONDS = 15        # Delay between requests
BATCH_SIZE = 1                    # Process one at a time for free tier

# Key Rotation
ROTATION_STRATEGY = "smart_rotate"  # round_robin, load_balance, smart_rotate
MIN_REQUESTS_PER_KEY = 5          # Switch key after N requests (edit as per your use case)

# Image Processing
MAX_IMAGE_SIZE_MB = 10            # Maximum image size
TARGET_IMAGE_SIZE = (2048, 2048)  # Target resolution

# Scheduling
SLEEP_START_HOUR = 0              # Midnight
SLEEP_END_HOUR = 6                # 6 AM - Process during off-peak
```

## 📊 Usage

### Basic Processing
```bash
# Process all images in images/ folder
python main.py

# With verbose logging
python main.py 2>&1 | tee ocr_processing.log
```

### Key Management
```bash
# List all API keys and their status
python manage_keys.py list

# Add a new API key
python manage_keys.py add "YOUR_API_KEY" --alias "my_key"

# Remove a key
python manage_keys.py remove "my_key"

# Test all API keys
python manage_keys.py test

# Show key statistics
python manage_keys.py stats
```

### Monitoring Progress
```bash
# Monitor logs in real-time
tail -f ocr_processing.log

# Check processing report
cat annotations/processing_report.json | python -m json.tool

# Check key statistics
cat api_key_stats.json | python -m json.tool
```

## 🎯 Performance Optimization

### For Free Tier Users
With 4 API keys on Gemini free tier:
- **Maximum throughput**: ~60 images/day
- **Safe throughput**: 40-50 images/day
- **Processing rate**: ~1 image every 15 seconds

### Tips for Better Results
1. **Use multiple API keys**: More keys = higher daily limit
2. **Schedule during off-peak**: 12 AM - 6 AM works best
3. **Preprocess images**: Ensure good scan quality
4. **Monitor logs**: Watch for rate limiting issues
5. **Rotate keys**: Use different keys for different days

## 📈 Output Structure

### Annotations Directory
```
annotations/
├── document1.txt              # Extracted text
├── document1.meta.json        # Processing metadata
├── document1.key_meta.json    # Key usage metadata
├── document2.txt
├── document2.meta.json
├── processing_report.json     # Overall statistics
└── api_key_stats.json        # Key performance metrics
```

### Sample Annotation File
```
[Start of extracted text]
नेपाल सरकार
शिक्षा मन्त्रालय
त्रिभुवन विश्वविद्यालय
...

प्रमाणपत्र
यो प्रमाणपत्रले प्रमाणित गर्दछ कि
श्री/सुश्री राम बहादुर कार्की ले
...

[End of extracted text]
```

## 🔧 Advanced Usage

### Docker Deployment
```bash
# Build Docker image
docker build -t nepali-ocr .

# Run with Docker
docker run -v ./images:/app/images \
           -v ./annotations:/app/annotations \
           -e GEMINI_API_KEY_1="your_key" \
           nepali-ocr

# Using docker-compose
docker-compose up
```

### Custom Processing Script
```python
from src.ocr_processor import GeminiOCRProcessor
from src.api_key_manager import APIKeyManager
from config.settings import config

# Custom processing
key_manager = APIKeyManager(config)
ocr = GeminiOCRProcessor(key_manager)

# Process single image
with open('image.jpg', 'rb') as f:
    image_bytes = f.read()

text, key_used = ocr.extract_text_from_image(image_bytes)
print(f"Extracted {len(text)} characters using key {key_used}")
```

### Integration with Other Systems
```python
import json
from pathlib import Path

# Load processed annotations
def load_annotations(annotation_dir):
    annotations = {}
    for txt_file in Path(annotation_dir).glob("*.txt"):
        with open(txt_file, 'r', encoding='utf-8') as f:
            text = f.read()
        annotations[txt_file.stem] = text
    return annotations

# Export to CSV
import pandas as pd
def export_to_csv(annotation_dir, output_csv):
    data = []
    for txt_file in Path(annotation_dir).glob("*.txt"):
        with open(txt_file, 'r', encoding='utf-8') as f:
            text = f.read()
        data.append({
            'filename': txt_file.stem,
            'text': text,
            'length': len(text)
        })
    df = pd.DataFrame(data)
    df.to_csv(output_csv, index=False, encoding='utf-8')
```

## 🐛 Troubleshooting

### Common Issues

1. **No API keys found**
   - Ensure `api_keys.json` exists and has valid keys
   - Or set environment variables
   - Run `python manage_keys.py test` to verify keys

2. **Rate limit errors**
   - Check `ocr_processing.log` for rate limit warnings
   - Increase `REQUEST_DELAY_SECONDS` in settings
   - Add more API keys

3. **Empty OCR results**
   - Verify image quality and size
   - Check if images contain Nepali text
   - Try manual preprocessing of images

4. **Memory issues**
   - Reduce `MAX_IMAGE_SIZE_MB` in settings
   - Process fewer images at once
   - Use smaller target image size

### Logs and Debugging
```bash
# View all errors
grep -i "error\|failed" ocr_processing.log

# Monitor rate limiting
grep -i "rate\|limit\|wait" ocr_processing.log

# Check key usage
grep -i "key.*used\|alias" ocr_processing.log

# View processing statistics
python -c "import json; print(json.dumps(json.load(open('annotations/processing_report.json')), indent=2))"
```

## 📚 API Reference

### Key Classes

#### `APIKeyManager`
Manages multiple API keys with rotation strategies.

```python
manager = APIKeyManager(config)
key = manager.get_next_key()  # Get next available key
stats = manager.monitor_keys()  # Get key statistics
```

#### `GeminiOCRProcessor`
Processes images through Gemini API.

```python
ocr = GeminiOCRProcessor(api_key_manager)
text, key_used = ocr.extract_text_from_image(image_bytes)
```

#### `SmartScheduler`
Manages rate limiting and scheduling.

```python
scheduler = SmartScheduler(config)
if scheduler.should_process():
    # Process image
    scheduler.wait_for_next_slot()
```

#### `ImagePreprocessor`
Enhances images for better OCR.

```python
preprocessor = ImagePreprocessor()
image_bytes = preprocessor.load_and_preprocess(image_path)
```

## 🔄 Rotation Strategies

1. **Round Robin**: Cycle through keys sequentially
2. **Load Balance**: Distribute based on usage count
3. **Smart Rotate**: Consider success rate, error count, and recent usage

Choose strategy in `config/settings.py`:
```python
ROTATION_STRATEGY = "smart_rotate"  # Most intelligent
```

## 📊 Performance Metrics

The system tracks:
- **Success rate**: Percentage of successful OCR extractions
- **Key utilization**: How many keys were used
- **Processing time**: Time per image and total duration
- **Error rate**: Types and frequencies of errors
- **Rate limit hits**: How often rate limits were encountered

View metrics in:
- `annotations/processing_report.json`
- `api_key_stats.json`
- `ocr_processing.log`

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Code formatting
black src/ config/ tests/
flake8 src/ config/ tests/
```

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google Gemini AI for providing the OCR capabilities
- Nepali language processing community
- Open source contributors

## 📞 Support

For issues, questions, or feature requests:
1. Check the [Troubleshooting](#troubleshooting) section
2. Search existing issues
3. Create a new issue with detailed information

---

**Happy OCR processing!** 🎉

*Note: This system is optimized for Nepali documents but can be adapted for other languages by modifying the prompt and language settings.*