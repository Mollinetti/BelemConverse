"""
Pydantic schemas for API request/response validation.
"""

from typing import Optional, List, Literal
from pydantic import BaseModel, Field


class LatLng(BaseModel):
    """Latitude/Longitude coordinates."""
    lat: float = Field(..., description="Latitude", ge=-90, le=90)
    lng: float = Field(..., description="Longitude", ge=-180, le=180)


class Coordinates(BaseModel):
    """User coordinates for location-based queries (legacy alias)."""
    lat: float = Field(..., description="Latitude", ge=-90, le=90)
    lng: float = Field(..., description="Longitude", ge=-180, le=180)


class ChatFilters(BaseModel):
    """Explicit filters for chat request."""
    placeType: Optional[List[str]] = Field(default=None, description="Place types to filter")
    city: Optional[str] = Field(default=None, description="City filter")
    neighborhood: Optional[str] = Field(default=None, description="Neighborhood filter")
    openNow: Optional[bool] = Field(default=None, description="Filter for places open now")
    priceMax: Optional[float] = Field(default=None, description="Maximum price")
    minRating: Optional[float] = Field(default=None, description="Minimum rating")
    minReviews: Optional[int] = Field(default=None, description="Minimum review count")


class ChatRequest(BaseModel):
    """Request body for chat endpoint per OpenAPI spec."""
    message: str = Field(..., min_length=1, max_length=2000, description="User message")
    language: Optional[Literal["en", "pt-BR"]] = Field(default=None, description="Response language")
    userLocation: Optional[LatLng] = Field(default=None, description="User location")
    nowIso: Optional[str] = Field(default=None, description="Client current time in ISO-8601")
    filters: Optional[ChatFilters] = Field(default=None, description="Explicit filters")
    
    # Legacy support
    coordinates: Optional[Coordinates] = Field(default=None, description="User location (legacy)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Quais são os melhores restaurantes perto de mim?",
                "language": "pt-BR",
                "userLocation": {"lat": -1.4695, "lng": -48.4665}
            }
        }


class ReviewsDistribution(BaseModel):
    """Reviews distribution."""
    oneStar: int = Field(default=0)
    twoStar: int = Field(default=0)
    threeStar: int = Field(default=0)
    fourStar: int = Field(default=0)
    fiveStar: int = Field(default=0)


class Place(BaseModel):
    """Canonical Place entity per OpenAPI spec."""
    placeId: str
    cid: Optional[str] = None
    fid: Optional[str] = None
    title: Optional[str] = None
    titleFormatted: Optional[str] = None
    subTitle: Optional[str] = None
    categoryName: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    address: Optional[str] = None
    addressFormatted: Optional[str] = None
    street: Optional[str] = None
    streetFormatted: Optional[str] = None
    neighborhood: Optional[str] = None
    locatedIn: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postalCode: Optional[str] = None
    countryCode: Optional[str] = None
    location: Optional[LatLng] = None
    phone: Optional[str] = None
    phoneUnformatted: Optional[str] = None
    url: Optional[str] = None
    website: Optional[str] = None
    googleFoodUrl: Optional[str] = None
    menu: Optional[str] = None
    reserveTableUrl: Optional[str] = None
    price: Optional[float] = None
    rank: Optional[float] = None
    totalScore: Optional[float] = None
    reviewsCount: Optional[int] = None
    reviewsDistribution: ReviewsDistribution = Field(default_factory=ReviewsDistribution)
    isSponsored: bool = Field(default=False)
    businessTime: Optional[str] = None
    place_type: Literal["restaurant", "bar", "park", "other"]


class PlaceResult(Place):
    """Place result with computed fields per OpenAPI spec."""
    distanceKm: Optional[float] = Field(default=None, description="Distance in km")
    openNowStatus: Optional[Literal["open", "closed", "unknown"]] = Field(
        default=None,
        description="Open now status"
    )


class PlaceLegacy(BaseModel):
    """Legacy Place schema for backward compatibility."""
    name: str
    address: Optional[str] = None
    category: Optional[str] = None
    rating: Optional[float] = None
    reviews_count: Optional[int] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    phone: Optional[str] = None
    distance_km: Optional[float] = None
    source: str = Field(default="database", description="Data source: database or osm_realtime")


class ChatResponse(BaseModel):
    """Response body for chat endpoint per OpenAPI spec."""
    language: Literal["en", "pt-BR"] = Field(..., description="Response language")
    answer: str = Field(..., description="LLM response text")
    results: List[PlaceResult] = Field(default_factory=list, max_items=5, description="Up to 5 place results")
    debug: Optional[dict] = Field(default=None, description="Debug information")
    
    # Legacy fields for backward compatibility
    response: Optional[str] = Field(default=None, description="LLM response text (legacy)")
    places: Optional[List[PlaceLegacy]] = Field(default=None, description="Extracted places (legacy)")
    source: Optional[str] = Field(default=None, description="Primary data source used (legacy)")
    processing_time_ms: Optional[float] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "language": "pt-BR",
                "answer": "Aqui estão os melhores restaurantes próximos...",
                "results": [
                    {
                        "placeId": "place_123",
                        "title": "Restaurante Amazônico",
                        "addressFormatted": "Av. Presidente Vargas, 123",
                        "categoryName": "Restaurant",
                        "totalScore": 4.5,
                        "location": {"lat": -1.4558, "lng": -48.4902},
                        "distanceKm": 0.5,
                        "openNowStatus": "open"
                    }
                ]
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str
    llm_loaded: bool
    vector_store_loaded: bool


class LanguagesResponse(BaseModel):
    """Available languages response."""
    languages: List[dict] = [
        {"code": "pt", "name": "Português"},
        {"code": "en", "name": "English"}
    ]
    default: str = "pt"


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: Optional[str] = None


class IngestionResponse(BaseModel):
    """Response for CSV ingestion endpoint."""
    ingestedCount: int = Field(..., description="Number of places successfully ingested")
    skippedCount: int = Field(..., description="Number of rows skipped")
    outputFiles: List[str] = Field(..., description="Paths to output files (canonical_places.jsonl, ingestion_report.json)")


