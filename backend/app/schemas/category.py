from pydantic import BaseModel


class CategoryOut(BaseModel):
    id: int
    name: str
    slug: str
    active: bool

    model_config = {"from_attributes": True}
