from pydantic import BaseModel


class DistrictRead(BaseModel):
    id: int
    name: str
    pinyin: str | None
    is_urban: bool
    listing_count: int = 0

    model_config = {"from_attributes": True}


class DistrictStats(BaseModel):
    id: int
    name: str
    listing_count: int = 0
    avg_total_price: float | None = None
    avg_unit_price: float | None = None
    median_unit_price: float | None = None

    model_config = {"from_attributes": True}
