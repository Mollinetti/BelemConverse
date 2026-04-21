"""
Enhanced Main script demonstrating TF-IDF RAG Agent integration.
This script shows how to use the new Enhanced RAG Agent with TF-IDF intent classification.
"""

import os
import sys
import logging
from typing import Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

import sys
import os

# Add project root to Python path  
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from belem_converse.core.enhanced_rag_agent import EnhancedRAGAgent
from belem_converse.ingest.vector_store import VectorStoreManager
from belem_converse.utils.models import ModelManager

logger = logging.getLogger(__name__)


class EnhancedTravelGuide:
    """
    Enhanced Travel Guide using TF-IDF intent classification and structured filtering.
    """
    
    def __init__(self):
        """Initialize the Enhanced Travel Guide."""
        logger.info("Initializing Enhanced Travel Guide with TF-IDF integration...")
        
        try:
            # Initialize vector store
            logger.info("Loading vector store...")
            self.vector_store_manager = VectorStoreManager()
            self.vector_store = self.vector_store_manager.initialize()
            
            # Initialize LLM
            logger.info("Loading LLM model...")
            self.llm_model = ModelManager.get_llm()
            
            # Initialize Enhanced RAG Agent
            logger.info("Setting up Enhanced RAG Agent...")
            self.rag_agent = EnhancedRAGAgent(
                vector_store_manager=self.vector_store_manager,
                llm_model=self.llm_model
            )
            
            logger.info("Enhanced Travel Guide initialized successfully!")
            
        except Exception as e:
            logger.error(f"Failed to initialize Enhanced Travel Guide: {e}")
            raise
    
    def ask(
        self, 
        question: str, 
        user_coordinates: Optional[Tuple[float, float]] = None,
        top_k: int = 5
    ) -> str:
        """
        Ask a question to the Enhanced Travel Guide.
        
        Args:
            question: User's question
            user_coordinates: Optional user coordinates (lat, lng)
            top_k: Number of results to return
            
        Returns:
            AI-generated response
        """
        try:
            logger.info(f"Processing question: '{question}'")
            
            response = self.rag_agent.query(
                question=question,
                user_coordinates=user_coordinates,
                top_k=top_k
            )
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return f"I'm sorry, I encountered an error: {e}"
    
    def get_performance_metrics(self):
        """Get performance metrics from the RAG agent."""
        return self.rag_agent.get_performance_metrics()
    
    def reset_metrics(self):
        """Reset performance metrics."""
        self.rag_agent.reset_performance_metrics()


def interactive_demo():
    """Run an interactive demo of the Enhanced Travel Guide."""
    print("🌟 Enhanced Travel Guide with TF-IDF Intent Classification")
    print("=" * 60)
    print("This demo showcases the improved RAG agent with:")
    print("✓ TF-IDF intent classification")
    print("✓ Structured filtering")
    print("✓ Optimized vector search")
    print("✓ Performance monitoring")
    print("=" * 60)
    
    try:
        # Initialize the enhanced travel guide
        guide = EnhancedTravelGuide()
        
        # Example coordinates (Belem, Brazil)
        belem_coords = (-1.4412191713305627, -48.46797987961913)
        
        # Demo queries with explanations
        demo_queries = [
            {
                'question': 'I need a good restaurant nearby',
                'coords': belem_coords,
                'explanation': 'Location + Category intent: Should filter by restaurant category and proximity'
            },
            {
                'question': 'Show me the best rated hotels',
                'coords': None,
                'explanation': 'Popularity + Category intent: Should filter by hotel category and sort by rating'
            },
            {
                'question': 'Preciso de um café para trabalhar com wifi',
                'coords': belem_coords,
                'explanation': 'Portuguese query: Category (cafe) + specific requirements (work, wifi)'
            },
            {
                'question': 'What tourist attractions are open now?',
                'coords': None,
                'explanation': 'Business hours + Category intent: Should filter by business hours and tourist attractions'
            },
            {
                'question': 'Onde posso encontrar açaí por aqui?',
                'coords': belem_coords,
                'explanation': 'Portuguese query: Location + Açaí category (special Brazilian category)'
            }
        ]
        
        print("\n🚀 Running Demo Queries...")
        print("=" * 60)
        
        for i, demo in enumerate(demo_queries, 1):
            print(f"\nDemo Query {i}:")
            print(f"Question: '{demo['question']}'")
            print(f"Explanation: {demo['explanation']}")
            if demo['coords']:
                print(f"Coordinates: {demo['coords']}")
            
            print("\nProcessing...")
            response = guide.ask(
                question=demo['question'],
                user_coordinates=demo['coords'],
                top_k=3
            )
            
            print(f"\nResponse:")
            print("-" * 40)
            print(response[:300] + "..." if len(response) > 300 else response)
            print("-" * 40)
            
            input("\nPress Enter to continue to next demo...")
        
        # Show performance metrics
        print("\n📊 Performance Metrics:")
        print("=" * 40)
        metrics = guide.get_performance_metrics()
        for metric, value in metrics.items():
            if isinstance(value, float):
                print(f"{metric}: {value:.3f}")
            else:
                print(f"{metric}: {value}")
        
        # Interactive mode
        print("\n🎯 Interactive Mode")
        print("=" * 40)
        print("You can now ask your own questions!")
        print("Type 'exit' to quit, 'metrics' to see performance, 'reset' to reset metrics")
        print("Example: 'I need a pizza place nearby' or 'Onde tem hotel barato?'")
        
        while True:
            try:
                question = input("\n🤔 Your question: ").strip()
                
                if question.lower() == 'exit':
                    break
                elif question.lower() == 'metrics':
                    metrics = guide.get_performance_metrics()
                    print("\nCurrent metrics:")
                    for metric, value in metrics.items():
                        if isinstance(value, float):
                            print(f"  {metric}: {value:.3f}")
                        else:
                            print(f"  {metric}: {value}")
                    continue
                elif question.lower() == 'reset':
                    guide.reset_metrics()
                    print("Metrics reset successfully!")
                    continue
                elif not question:
                    continue
                
                # Ask if user wants to provide coordinates
                coords_input = input("📍 Your coordinates (lat,lng) or press Enter to skip: ").strip()
                user_coords = None
                
                if coords_input:
                    try:
                        lat, lng = map(float, coords_input.split(','))
                        user_coords = (lat, lng)
                        print(f"Using coordinates: {user_coords}")
                    except ValueError:
                        print("Invalid coordinates format, skipping location context")
                
                print("\n🤖 Processing your question...")
                response = guide.ask(question, user_coords)
                
                print(f"\n💬 Response:")
                print("-" * 50)
                print(response)
                print("-" * 50)
                
            except KeyboardInterrupt:
                print("\n\nGoodbye! 👋")
                break
            except Exception as e:
                print(f"\nError: {e}")
                continue
    
    except Exception as e:
        print(f"Failed to start demo: {e}")
        return 1
    
    return 0


def simple_example():
    """Show a simple usage example."""
    print("Simple Usage Example:")
    print("-" * 30)
    
    try:
        # Initialize
        guide = EnhancedTravelGuide()
        
        # Ask a question
        question = "I need a good restaurant for dinner"
        user_location = (-8.0476, -34.8770)  # belem, Brazil
        
        response = guide.ask(question, user_location)
        print(f"Question: {question}")
        print(f"Response: {response}")
        
        # Show metrics
        metrics = guide.get_performance_metrics()
        print(f"\nPerformance: {metrics['avg_total_time']:.3f}s total")
        
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Enhanced Travel Guide with TF-IDF")
    parser.add_argument("--demo", action="store_true", help="Run interactive demo")
    parser.add_argument("--simple", action="store_true", help="Run simple example")
    parser.add_argument("--question", type=str, help="Ask a specific question")
    parser.add_argument("--coords", type=str, help="User coordinates (lat,lng)")
    
    args = parser.parse_args()
    
    if args.demo:
        exit(interactive_demo())
    elif args.simple:
        simple_example()
    elif args.question:
        try:
            guide = EnhancedTravelGuide()
            
            user_coords = None
            if args.coords:
                lat, lng = map(float, args.coords.split(','))
                user_coords = (lat, lng)
            
            response = guide.ask(args.question, user_coords)
            print(response)
            
        except Exception as e:
            print(f"Error: {e}")
            exit(1)
    else:
        print("Enhanced Travel Guide - TF-IDF Integration")
        print("Usage examples:")
        print("  python enhanced_main.py --demo          # Interactive demo")
        print("  python enhanced_main.py --simple        # Simple example")
        print("  python enhanced_main.py --question 'what are the closest ice cream shops?' --coords '-1.4412191713305627,-48.46797987961913'")
        print("\nFor full interactive demo: python enhanced_main.py --demo") 