from typing import List, Optional, Union

from pydantic import BaseModel, Field


class UserListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    username: Optional[str] = Field(None, description="账号模糊搜索")
    gender: Optional[str] = Field(None, description="性别字典值，如 1/2/3")


class UserExportBody(BaseModel):
    username: Optional[str] = Field(None, description="账号模糊搜索")
    gender: Optional[str] = Field(None, description="性别字典值，如 1/2/3")


class UserAddBody(BaseModel):
    username: str = Field(..., min_length=1, description="登录账号")
    password: str = Field(..., min_length=1, description="明文密码")
    nickname: Optional[str] = Field(None, description="昵称")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机")
    gender: Optional[str] = Field("3", description="性别字典值，默认 3 未知")
    roleIds: List[int] = Field(default_factory=list, description="角色 ID 列表")


class UserDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除用户 ID 列表")


class UserEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="用户 ID")
    username: Optional[str] = Field(None, description="登录账号")
    nickname: Optional[str] = Field(None, description="昵称")
    email: Optional[str] = Field(None, description="邮箱")
    phone: Optional[str] = Field(None, description="手机")
    gender: Optional[str] = Field(None, description="性别字典值")
    roleIds: List[int] = Field(default_factory=list, description="角色 ID 列表")


class UserChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="用户 ID")
    status: int = Field(..., description="1 启用 0 禁用")


class UserChangePasswordBody(BaseModel):
    oldPassword: str = Field(..., min_length=1, description="旧密码")
    newPassword: str = Field(..., min_length=1, description="新密码")
