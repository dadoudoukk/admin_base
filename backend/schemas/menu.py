from typing import Optional, Union

from pydantic import BaseModel, Field

MENU_TYPES = frozenset({"CATALOG", "MENU", "BUTTON"})


class MenuAddBody(BaseModel):
    parentId: Optional[int] = Field(None, description="父级菜单 ID，根节点不传")
    menuType: str = Field("MENU", description="CATALOG / MENU / BUTTON")
    name: str = Field(..., min_length=1, description="路由 name")
    title: str = Field(..., min_length=1, description="显示标题")
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    permission: Optional[str] = None
    sort: int = 0
    remark: Optional[str] = None


class MenuEditBody(BaseModel):
    id: Union[str, int]
    parentId: Optional[int] = None
    menuType: Optional[str] = None
    name: Optional[str] = None
    title: Optional[str] = None
    path: Optional[str] = None
    component: Optional[str] = None
    icon: Optional[str] = None
    permission: Optional[str] = None
    sort: Optional[int] = None
    remark: Optional[str] = None
    status: Optional[bool] = None


class MenuDeleteBody(BaseModel):
    id: Union[str, int] = Field(..., description="菜单 ID")
