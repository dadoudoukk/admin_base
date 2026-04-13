from typing import List, Optional, Union

from pydantic import BaseModel, ConfigDict, Field


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


class SysApiListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    apiPath: Optional[str] = Field(None, description="接口路径模糊搜索")
    apiMethod: Optional[str] = Field(None, description="请求方式")
    apiModule: Optional[str] = Field(None, description="所属模块")


class SysApiCreateBody(BaseModel):
    api_path: str = Field(..., min_length=1, description="接口路径")
    api_method: str = Field(..., min_length=1, description="请求方式")
    api_name: Optional[str] = Field(None, description="接口名称")
    api_module: Optional[str] = Field(None, description="所属模块")
    status: bool = Field(True, description="是否启用")
    auth_required: bool = Field(True, description="是否鉴权")
    log_required: bool = Field(False, description="是否记录日志")
    rate_limit: int = Field(0, ge=0, description="限流QPS，0不限流")
    remark: Optional[str] = Field(None, description="备注")


class SysApiUpdateBody(BaseModel):
    id: Union[str, int] = Field(..., description="接口配置ID")
    api_name: Optional[str] = Field(None, description="接口名称")
    api_module: Optional[str] = Field(None, description="所属模块")
    status: Optional[bool] = Field(None, description="是否启用")
    auth_required: Optional[bool] = Field(None, description="是否鉴权")
    log_required: Optional[bool] = Field(None, description="是否记录日志")
    rate_limit: Optional[int] = Field(None, ge=0, description="限流QPS，0不限流")
    remark: Optional[str] = Field(None, description="备注")


class SysApiChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="接口配置ID")
    field: str = Field(..., description="开关字段 status/auth_required/log_required")
    value: Union[bool, int] = Field(..., description="开关值 true/false 或 1/0")


class SysApiResponse(BaseModel):
    id: Union[str, int]
    apiPath: str
    apiMethod: str
    apiName: str
    apiModule: str
    status: int
    authRequired: int
    logRequired: int
    rateLimit: int
    remark: str
    createTime: str
    updateTime: str


class SysConfigCreate(BaseModel):
    config_name: str = Field(..., min_length=1, description="配置名称")
    config_key: str = Field(..., min_length=1, description="配置键名，唯一")
    config_value: Optional[str] = Field(None, description="配置键值")
    config_type: str = Field("text", min_length=1, max_length=32, description="前端渲染类型")
    remark: Optional[str] = Field(None, description="备注")


class SysConfigUpdate(BaseModel):
    config_name: Optional[str] = Field(None, description="配置名称")
    config_value: Optional[str] = Field(None, description="配置键值")
    config_type: Optional[str] = Field(None, max_length=32, description="前端渲染类型")
    remark: Optional[str] = Field(None, description="备注")


class SysConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    config_name: str
    config_key: str
    config_value: Optional[str]
    config_type: str
    remark: Optional[str]


class SysConfigBatchItem(BaseModel):
    config_key: str = Field(..., min_length=1, description="要更新的配置键名")
    config_value: Optional[str] = Field(None, description="新键值")


class SysConfigBatchUpdate(BaseModel):
    items: List[SysConfigBatchItem] = Field(..., min_length=1, description="按 config_key 批量更新键值")
