from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)


class OrganizationOut(BaseModel):
    id: str
    name: str

    model_config = {"from_attributes": True}


class MembershipOut(BaseModel):
    organization_id: str
    user_id: str
    role: str

    model_config = {"from_attributes": True}


class MembershipUpdate(BaseModel):
    role: str = Field(pattern="^(owner|manager|viewer)$")


class OrganizationDetail(BaseModel):
    id: str
    name: str
    members: list[MembershipOut] = []

    model_config = {"from_attributes": True}
