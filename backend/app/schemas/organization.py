from pydantic import BaseModel, Field, field_validator

from app.models.enums import OrganizationKind


def _clean_name(value: str | None) -> str | None:
    # Validated after trimming, so "   " can't become a blank organisation.
    if value is None:
        return None
    value = " ".join(value.split())
    if not value:
        raise ValueError("Name can't be blank")
    return value


class OrganizationOut(BaseModel):
    id: int
    name: str
    kind: OrganizationKind
    active: bool

    model_config = {"from_attributes": True}


class OrganizationCreate(BaseModel):
    name: str = Field(max_length=255)
    kind: OrganizationKind

    _name = field_validator("name")(_clean_name)


class OrganizationPatch(BaseModel):
    name: str | None = Field(None, max_length=255)
    kind: OrganizationKind | None = None
    active: bool | None = None

    _name = field_validator("name")(_clean_name)
