"""
Bayesian Average Rating System for Enhanced RAG Agent.
Implements statistically sound popularity ranking that considers both rating and review count.

Based on research by Evan Miller:
- https://www.evanmiller.org/bayesian-average-ratings.html
- https://www.evanmiller.org/ranking-items-with-star-ratings.html
"""

import math
import logging
from typing import Dict, Any, List, Optional
from scipy import stats
import numpy as np

logger = logging.getLogger(__name__)


class BayesianRankingSystem:
    """
    Bayesian ranking system that properly weighs ratings by statistical confidence.
    Addresses the problem where 5.0 stars with 1 review beats 4.0 stars with 100 reviews.
    """
    
    def __init__(self):
        # Configuration parameters
        self.confidence_level = 0.95  # 95% confidence interval
        self.z_score = 1.96  # For 95% confidence (can use 1.65 for 90%)
        
        # Prior parameters for Bayesian estimation
        # These represent our "default belief" before seeing any data
        self.prior_mean = 3.0  # Assume average rating is 3.0 stars (neutral)
        self.prior_weight = 5  # Equivalent to 5 prior observations
        
        # Minimum review threshold for displaying ratings
        self.min_reviews_to_display = 3
        
        # Rating scale parameters
        self.min_rating = 1.0
        self.max_rating = 5.0
        
    def calculate_bayesian_average(
        self, 
        rating: float, 
        review_count: int,
        prior_mean: Optional[float] = None,
        prior_weight: Optional[int] = None
    ) -> float:
        """
        Calculate Bayesian average rating that accounts for review count.
        
        Formula: (prior_weight * prior_mean + review_count * rating) / (prior_weight + review_count)
        
        Args:
            rating: Average star rating (1.0 to 5.0)
            review_count: Number of reviews
            prior_mean: Prior belief about average rating (default: self.prior_mean)
            prior_weight: Weight of prior belief (default: self.prior_weight)
            
        Returns:
            Bayesian average rating
        """
        if prior_mean is None:
            prior_mean = self.prior_mean
        if prior_weight is None:
            prior_weight = self.prior_weight
            
        # Handle edge cases
        if review_count <= 0:
            return prior_mean
        if rating < self.min_rating or rating > self.max_rating:
            logger.warning(f"Rating {rating} outside expected range [{self.min_rating}, {self.max_rating}]")
            rating = max(self.min_rating, min(self.max_rating, rating))
        
        # Calculate Bayesian average
        bayesian_avg = (prior_weight * prior_mean + review_count * rating) / (prior_weight + review_count)
        
        return bayesian_avg
    
    def calculate_confidence_score(
        self, 
        rating: float, 
        review_count: int
    ) -> float:
        """
        Calculate confidence score based on statistical significance.
        Higher review counts get higher confidence scores.
        
        Args:
            rating: Average star rating
            review_count: Number of reviews
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if review_count <= 0:
            return 0.0
        
        # Use logarithmic scaling for confidence - diminishing returns with more reviews
        # Formula: 1 - exp(-review_count / scale_factor)
        scale_factor = 20  # Adjust this to change how quickly confidence saturates
        confidence = 1.0 - math.exp(-review_count / scale_factor)
        
        return confidence
    
    def calculate_lower_bound_rating(
        self, 
        rating: float, 
        review_count: int
    ) -> float:
        """
        Calculate lower bound of confidence interval for rating.
        This is the "conservative" estimate - we're 95% confident the true rating is above this.
        
        Based on Wilson score interval for ratings.
        
        Args:
            rating: Average star rating
            review_count: Number of reviews
            
        Returns:
            Lower bound rating
        """
        if review_count <= 0:
            return self.prior_mean
        
        # Convert rating to proportion (0 to 1 scale)
        p = (rating - self.min_rating) / (self.max_rating - self.min_rating)
        n = review_count
        z = self.z_score
        
        # Wilson score interval lower bound
        # Formula: (p + z²/(2n) - z*sqrt(p(1-p)/n + z²/(4n²))) / (1 + z²/n)
        try:
            denominator = 1 + z*z/n
            p_hat = p + z*z/(2*n)
            margin = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))
            
            lower_bound_proportion = (p_hat - margin) / denominator
            
            # Convert back to rating scale
            lower_bound_rating = lower_bound_proportion * (self.max_rating - self.min_rating) + self.min_rating
            
            # Ensure within bounds
            lower_bound_rating = max(self.min_rating, min(self.max_rating, lower_bound_rating))
            
            return lower_bound_rating
            
        except (ZeroDivisionError, ValueError, OverflowError) as e:
            logger.warning(f"Error calculating lower bound for rating={rating}, count={review_count}: {e}")
            return self.prior_mean
    
    def calculate_popularity_score(
        self, 
        rating: float, 
        review_count: int,
        method: str = "bayesian_lower_bound"
    ) -> float:
        """
        Calculate overall popularity score using specified method.
        
        Args:
            rating: Average star rating
            review_count: Number of reviews  
            method: Scoring method ("bayesian_avg", "lower_bound", "bayesian_lower_bound")
            
        Returns:
            Popularity score
        """
        if method == "bayesian_avg":
            return self.calculate_bayesian_average(rating, review_count)
        
        elif method == "lower_bound":
            return self.calculate_lower_bound_rating(rating, review_count)
        
        elif method == "bayesian_lower_bound":
            # Hybrid approach: Use Bayesian average, then apply confidence penalty
            bayesian_avg = self.calculate_bayesian_average(rating, review_count)
            lower_bound = self.calculate_lower_bound_rating(bayesian_avg, review_count)
            return lower_bound
            
        else:
            logger.warning(f"Unknown scoring method: {method}. Using bayesian_lower_bound.")
            return self.calculate_popularity_score(rating, review_count, "bayesian_lower_bound")
    
    def should_display_rating(self, review_count: int) -> bool:
        """
        Determine if a rating should be displayed based on statistical confidence.
        
        Args:
            review_count: Number of reviews
            
        Returns:
            True if rating should be displayed
        """
        return review_count >= self.min_reviews_to_display
    
    def rank_places_by_popularity(
        self, 
        places: List[Dict[str, Any]],
        method: str = "bayesian_lower_bound"
    ) -> List[Dict[str, Any]]:
        """
        Rank places by popularity using Bayesian methods.
        
        Args:
            places: List of place dictionaries with 'rating' and 'user_ratings_total' fields
            method: Scoring method to use
            
        Returns:
            List of places sorted by popularity score (highest first)
        """
        scored_places = []
        
        for place in places:
            try:
                # Extract rating and review count
                rating = float(place.get('rating', 0))
                review_count = int(place.get('user_ratings_total', 0))
                
                # Calculate popularity score
                popularity_score = self.calculate_popularity_score(rating, review_count, method)
                
                # Add score to place data
                place_with_score = place.copy()
                place_with_score['popularity_score'] = popularity_score
                place_with_score['confidence_score'] = self.calculate_confidence_score(rating, review_count)
                place_with_score['should_display_rating'] = self.should_display_rating(review_count)
                
                scored_places.append(place_with_score)
                
            except (ValueError, TypeError) as e:
                logger.warning(f"Error scoring place {place.get('name', 'Unknown')}: {e}")
                # Add with default low score
                place_with_score = place.copy()
                place_with_score['popularity_score'] = self.prior_mean
                place_with_score['confidence_score'] = 0.0
                place_with_score['should_display_rating'] = False
                scored_places.append(place_with_score)
        
        # Sort by popularity score (descending)
        scored_places.sort(key=lambda x: x['popularity_score'], reverse=True)
        
        return scored_places
    
    def explain_ranking(
        self, 
        rating: float, 
        review_count: int,
        method: str = "bayesian_lower_bound"
    ) -> str:
        """
        Provide human-readable explanation of how a rating was scored.
        
        Args:
            rating: Average star rating
            review_count: Number of reviews
            method: Scoring method used
            
        Returns:
            Explanation string
        """
        popularity_score = self.calculate_popularity_score(rating, review_count, method)
        confidence_score = self.calculate_confidence_score(rating, review_count)
        bayesian_avg = self.calculate_bayesian_average(rating, review_count)
        
        explanation = f"""Rating Analysis:
• Original Rating: {rating:.1f}★ ({review_count} reviews)
• Bayesian Average: {bayesian_avg:.2f}★
• Popularity Score: {popularity_score:.2f}★
• Confidence Level: {confidence_score:.1%}
• Display Rating: {self.should_display_rating(review_count)}

Interpretation: """
        
        if review_count < self.min_reviews_to_display:
            explanation += f"Too few reviews ({review_count} < {self.min_reviews_to_display}) for reliable ranking."
        elif confidence_score < 0.5:
            explanation += "Moderate confidence - more reviews would improve ranking."
        elif confidence_score < 0.8:
            explanation += "Good confidence - well-established rating."
        else:
            explanation += "High confidence - very reliable rating."
            
        return explanation


# Global instance for easy access
bayesian_ranker = BayesianRankingSystem() 