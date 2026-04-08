from typing import List, Optional, Union

from pydantic import BaseModel, Field


class RoleListBody(BaseModel):
    pageNum: int = Field(1, ge=1)
    pageSize: int = Field(10, ge=1, le=200)
    roleName: Optional[str] = Field(None, description="角色名称模糊")
    roleCode: Optional[str] = Field(None, description="角色标识模糊")


class RoleAddBody(BaseModel):
    roleName: str = Field(..., min_length=1, description="角色名称")
    roleCode: str = Field(..., min_length=1, description="角色标识")
    remark: Optional[str] = Field(None, description="备注")


class RoleEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="角色 ID")
    roleName: str = Field(..., min_length=1)
    roleCode: str = Field(..., min_length=1)
    remark: Optional[str] = Field(None, description="备注")


class RoleDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="角色 ID 列表")


class RoleMenuIdsBody(BaseModel):
    roleId: Union[str, int] = Field(..., description="角色 ID")


class RoleAssignMenuBody(BaseModel):
    roleId: Union[str, int] = Field(..., description="角色 ID")
    menuIds: List[int] = Field(default_factory=list, description="菜单 ID 列表")
