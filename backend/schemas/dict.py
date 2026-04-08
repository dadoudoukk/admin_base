from typing import List, Optional, Union

from pydantic import BaseModel, Field


class DictTypeListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    dictName: Optional[str] = Field(None, description="字典名称模糊搜索")
    dictCode: Optional[str] = Field(None, description="字典编码模糊搜索")


class DictTypeAddBody(BaseModel):
    dictName: str = Field(..., min_length=1, description="字典名称")
    dictCode: str = Field(..., min_length=1, description="字典编码")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictTypeEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典类型 ID")
    dictName: str = Field(..., min_length=1, description="字典名称")
    dictCode: str = Field(..., min_length=1, description="字典编码")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictTypeDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除字典类型 ID 列表")


class DictTypeChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典类型 ID")
    status: Union[bool, int] = Field(..., description="状态（true/false 或 1/0）")


class DictDataListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    dictCode: str = Field(..., min_length=1, description="字典编码（必填）")
    dictLabel: Optional[str] = Field(None, description="字典标签模糊搜索")
    dictValue: Optional[str] = Field(None, description="字典值模糊搜索")


class DictDataAddBody(BaseModel):
    dictCode: str = Field(..., min_length=1, description="字典编码")
    dictLabel: str = Field(..., min_length=1, description="字典标签")
    dictValue: str = Field(..., min_length=1, description="字典值")
    sort: int = Field(0, description="排序")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictDataEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典数据 ID")
    dictCode: str = Field(..., min_length=1, description="字典编码")
    dictLabel: str = Field(..., min_length=1, description="字典标签")
    dictValue: str = Field(..., min_length=1, description="字典值")
    sort: int = Field(0, description="排序")
    status: Optional[bool] = Field(True, description="状态")
    remark: Optional[str] = Field(None, description="备注")


class DictDataDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除字典数据 ID 列表")


class DictDataChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="字典数据 ID")
    status: Union[bool, int] = Field(..., description="状态（true/false 或 1/0）")
