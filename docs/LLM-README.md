# RAG Travel Guide Chatbot with LangChain Tool Calling

A sophisticated travel guide chatbot that uses Retrieval Augmented Generation (RAG) combined with LangChain's automatic tool calling mechanism for intelligent location-based recommendations, popularity analysis, and business hours information.

## 🚀 Key Features

### LangChain Tool Calling Integration
- **Automatic Tool Selection**: The LLM automatically chooses and calls appropriate tools based on user queries
- **Intent Detection**: Built-in tools for detecting location, popularity, business hours, category, and price intents
- **Distance Calculation**: H3-based distance calculation for accurate urban distance measurement
- **Popularity Scoring**: Weighted scoring based on reviews, ratings, and rankings
- **Business Hours**: Extraction and formatting of business hours information
- **Multi-Category Support**: Support for multiple categories per place (categories/0 through categories/8)

### Core Capabilities
- **Location-Based Search**: Find places near user coordinates with distance calculations
- **Popularity-Based Recommendations**: Get the most popular and highly-rated places
- **Business Hours Information**: Access opening hours and schedules
- **Category Filtering**: Filter by specific types of places (restaurants, bars, hotels, etc.)
- **Price Level Filtering**: Find cheap or expensive options
- **Combined Queries**: Intelligent combination of location and popularity for best recommendations

## 🏗️ Architecture

### LangChain Tool Calling Flow
```
User Query → LLM with Bound Tools → Automatic Tool Selection → Tool Execution → Formatted Response
```

### Available Tools
1. **Distance & Location Tools**:
   - `calculate_distance`: H3-based distance calculation
   - `extract_coordinates_from_text`: Extract lat/lng from text
   - `find_closest_places`: Find nearest places to user location
   - `detect_location_intent`: Detect location-based queries

2. **Popularity Tools**:
   - `calculate_popularity_score`: Weighted popularity scoring
   - `find_most_popular_places`: Get top-rated places
   - `detect_popularity_intent`: Detect popularity-based queries

3. **Business Hours Tools**:
   - `get_business_hours`: Extract and format business hours
   - `find_places_with_business_hours`: Places with hours info
   - `detect_business_hours_intent`: Detect hours-related queries

4. **Category & Price Tools**:
   - `detect_category_intent`: Detect specific place categories
   - `detect_price_intent`: Detect price level preferences

5. **Response Formatting Tools**:
   - `format_distance_response`: Format location-based results
   - `format_popularity_response`: Format popularity-based results
   - `format_combined_response`: Format combined location+popularity results
   - `format_business_hours_response`: Format business hours results

## 📦 Installation

### Prerequisites
- Python 3.8+
- CUDA-compatible GPU (recommended)
- 8GB+ RAM

### Setup
```bash
# Clone the repository
git clone <repository-url>
cd LLM

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download models (see Models section below)
```

### Models Setup
1. **LLM Model**: Download a GGUF model (e.g., Mistral-7B-Instruct) to `models/llm/`
2. **Embedding Model**: Download sentence-transformers model to `models/embedding/`
3. **Data**: Place your CSV data in `data/csvs/`

## 🗂️ Data Format

Your CSV should include these columns for full functionality:

### Required Columns
- `title`: Place name
- `titleFormatted`: Formatted place name
- `address`: Full address
- `addressFormatted`: Formatted address
- `categoryName`: Primary category
- `categories/0` through `categories/8`: Multiple categories
- `location/lat`: Latitude
- `location/lng`: Longitude
- `reviewsCount`: Number of reviews
- `reviewsDistribution/fiveStar`: 5-star reviews count
- `reviewsDistribution/fourStar`: 4-star reviews count
- `reviewsDistribution/threeStar`: 3-star reviews count
- `reviewsDistribution/twoStar`: 2-star reviews count
- `reviewsDistribution/oneStar`: 1-star reviews count
- `rank`: Place ranking
- `businessTime`: Business hours information
- `price`: Price level indicator

## 🚀 Usage

### Basic Usage
```python
from src.agent.models import ModelManager
from src.agent.vector_store import VectorStoreManager
from src.agent.rag_agent import RAGAgent
from src.agent.config import get_config

# Initialize components
config = get_config()
model_manager = ModelManager()
llm_model = model_manager.get_llm()
vector_store_manager = VectorStoreManager()

# Create RAG agent with tool calling
agent = RAGAgent(vector_store_manager, llm_model)

# Query with automatic tool calling
response = agent.query(
    question="Find the best restaurants near me",
    user_coordinates=(-23.5505, -46.6333),  # São Paulo
    top_k=5
)
print(response)
```

### Example Queries

#### Location-Based Queries
```python
# Find closest places
response = agent.query("closest bars to my location", user_coordinates=(lat, lng))

# Find places within distance
response = agent.query("restaurants near me", user_coordinates=(lat, lng))
```

#### Popularity-Based Queries
```python
# Most popular places
response = agent.query("most popular restaurants")

# Top-rated places
response = agent.query("best rated hotels")
```

#### Business Hours Queries
```python
# Places with opening hours
response = agent.query("places with business hours")

# Opening times
response = agent.query("when do restaurants open")
```

#### Category-Based Queries
```python
# Specific categories
response = agent.query("best bars in the area")
response = agent.query("find museums")
response = agent.query("hotels with good ratings")
```

#### Price-Based Queries
```python
# Price levels
response = agent.query("cheap restaurants")
response = agent.query("expensive hotels")
```

#### Combined Queries
```python
# Location + popularity
response = agent.query("best restaurants near me", user_coordinates=(lat, lng))

# Category + location
response = agent.query("closest bars to my location", user_coordinates=(lat, lng))
```

## 🧪 Testing

### Run Tool Calling Tests
```bash
python test_tool_calling.py
```

### Run Interactive Demo
```bash
python src/agent/example_tool_calling.py
```

### Run Unit Tests
```bash
python -m pytest tests/ -v
```

## 🔧 Configuration

### Model Configuration
Edit `src/agent/config.py` to customize:
- LLM model path and parameters
- Embedding model settings
- Vector store configuration
- Data file paths

### Tool Configuration
Tools are automatically configured with LangChain's `@tool` decorator:
- Automatic parameter validation
- Type hints for better LLM understanding
- Structured input/output schemas

## 🏗️ Project Structure

```
LLM/
├── src/agent/
│   ├── tools.py              # LangChain tool definitions
│   ├── rag_agent.py          # RAG agent with tool calling
│   ├── models.py             # Model management
│   ├── vector_store.py       # Vector store operations
│   ├── config.py             # Configuration settings
│   └── examples/             # Usage examples
├── data/
│   ├── csvs/                 # CSV data files
│   └── chroma_db/            # Vector database
├── models/                   # Downloaded models
├── tests/                    # Test files
└── requirements.txt          # Dependencies
```

## 🔄 Migration from Manual Tool Calling

### What Changed
- **Before**: Manual intent detection and function calling
- **After**: Automatic tool calling via LangChain's `bind_tools()`

### Benefits of New Approach
1. **Automatic Tool Selection**: LLM chooses appropriate tools
2. **Better Error Handling**: Structured tool execution
3. **Type Safety**: Pydantic validation for tool parameters
4. **Extensibility**: Easy to add new tools
5. **Standardization**: Follows LangChain best practices

### Code Comparison

#### Old Manual Approach
```python
# Manual intent detection
intent = detect_query_intent(question)
if intent['location_based']:
    result = find_closest_places(coordinates, places_data)
    return format_distance_response(result)
```

#### New LangChain Approach
```python
# Automatic tool calling
response = model_with_tools.invoke({"question": question})
if response.tool_calls:
    return process_tool_calls(response.tool_calls, places_data)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- LangChain for the excellent tool calling framework
- Uber's H3 library for accurate distance calculations
- The open-source community for various dependencies

## 📞 Support

For issues and questions:
1. Check the existing issues
2. Create a new issue with detailed information
3. Include error messages and system information 