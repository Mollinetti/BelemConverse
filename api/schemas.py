"""
Pydantic schemas for API request/response validation.
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from belem_converse import gate


class LatLng(BaseModel):
    """Latitude/Longitude coordinates."""
    lat: float = Field(..., description="Latitude", ge=-90, le=90)
    lng: float = Field(..., description="Longitude", ge=-180, le=180)


class ChatFilters(BaseModel):
    """Explicit filters for chat request."""
    placeType: list[Annotated[str, Field(max_length=50)]] | None = Field(
        default=None, max_length=10, description="Place types to filter"
    )
    city: str | None = Field(default=None, max_length=100, description="City filter")
    neighborhood: str | None = Field(default=None, max_length=100, description="Neighborhood filter")
    openNow: bool | None = Field(default=None, description="Filter for places open now")
    priceMax: float | None = Field(default=None, description="Maximum price")
    minRating: float | None = Field(default=None, description="Minimum rating")
    minReviews: int | None = Field(default=None, description="Minimum review count")


class ChatRequest(BaseModel):
    """Request body for chat endpoint per OpenAPI spec."""
    session_id: UUID = Field(..., description="Conversation id: a UUID the client makes per conversation")
    message: str | None = Field(
        default=None,
        description="Visitor question: letters, digits, spaces and , . : ? ! only; required unless action is 'more'",
        json_schema_extra={"maxLength": gate.MAX_LEN},
    )
    action: Literal["more"] | None = Field(
        default=None, description="'more': the next results of the last answer, free of charge"
    )
    language: Literal["en", "pt-BR"] | None = Field(default=None, description="Response language")
    userLocation: LatLng | None = Field(default=None, description="User location")
    nowIso: str | None = Field(default=None, description="Client current time in ISO-8601")
    filters: ChatFilters | None = Field(default=None, description="Explicit filters")
    
    @model_validator(mode="after")
    def _gate(self):
        """The input gate; a GateError becomes a 422 in the request's language."""
        if self.message is None:
            if self.action != "more":
                raise gate.GateError("empty", self.language)
            return self
        self.message = gate.clean_message(self.message, language=self.language)
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "session_id": "3f1c2b9e-8d4a-4c6e-9b1a-2e7f5d0c4a11",
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
    cid: str | None = None
    fid: str | None = None
    title: str | None = None
    titleFormatted: str | None = None
    subTitle: str | None = None
    categoryName: str | None = None
    categories: list[str] = Field(default_factory=list)
    address: str | None = None
    addressFormatted: str | None = None
    street: str | None = None
    streetFormatted: str | None = None
    neighborhood: str | None = None
    locatedIn: str | None = None
    city: str | None = None
    state: str | None = None
    postalCode: str | None = None
    countryCode: str | None = None
    location: LatLng | None = None
    phone: str | None = None
    phoneUnformatted: str | None = None
    url: str | None = None
    website: str | None = None
    googleFoodUrl: str | None = None
    menu: str | None = None
    reserveTableUrl: str | None = None
    price: float | None = None
    rank: float | None = None
    totalScore: float | None = None
    reviewsCount: int | None = None
    reviewsDistribution: ReviewsDistribution = Field(default_factory=ReviewsDistribution)
    isSponsored: bool = Field(default=False)
    businessTime: str | None = None
    place_type: Literal["restaurant", "bar", "park", "other"]


class PlaceResult(Place):
    """Place result with computed fields per OpenAPI spec."""
    distanceKm: float | None = Field(default=None, description="Distance in km")
    openNowStatus: Literal["open", "closed", "unknown"] | None = Field(
        default=None,
        description="Open now status"
    )


class ChatResponse(BaseModel):
    """Response body for chat endpoint per OpenAPI spec."""
    language: Literal["en", "pt-BR"] = Field(..., description="Response language")
    answer: str = Field(..., description="LLM response text")
    results: list[PlaceResult] = Field(default_factory=list, max_items=5, description="Up to 5 place results")
    turns_left: int = Field(..., ge=0, description="Questions left in this conversation")
    has_more: bool = Field(default=False, description="More results to see with action 'more'")
    follow_ups: list[str] = Field(default_factory=list, description="Suggested next questions")
    debug: dict | None = Field(default=None, description="Debug information")
    processing_time_ms: float | None = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "language": "pt-BR",
                "answer": "Aqui estão os melhores restaurantes próximos...",
                "turns_left": 3,
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


class ErrorResponse(BaseModel):
    """Error response."""
    error: str
    detail: str | None = None


