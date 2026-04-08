from typing import Optional

from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, description="登录账号")
    password: str = Field(..., min_length=1, description="明文密码")


class SysOperLogListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    userName: Optional[str] = Field(None, description="操作人模糊搜索")
    requestMethod: Optional[str] = Field(None, description="请求方式，如 POST")


class SysOperLogExportBody(BaseModel):
    userName: Optional[str] = Field(None, description="操作人模糊搜索")
    requestMethod: Optional[str] = Field(None, description="请求方式，如 POST")
    startTime: Optional[str] = Field(None, description="开始时间，格式 YYYY-MM-DD HH:mm:ss")
    endTime: Optional[str] = Field(None, description="结束时间，格式 YYYY-MM-DD HH:mm:ss")
