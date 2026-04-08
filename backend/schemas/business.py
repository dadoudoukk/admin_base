from typing import List, Optional, Union

from pydantic import BaseModel, Field


class NewsCategoryListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    categoryName: Optional[str] = Field(None, description="分类名称模糊搜索")


class NewsCategoryAddBody(BaseModel):
    categoryName: str = Field(..., min_length=1, description="分类名称")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0停用 1启用")
    remark: Optional[str] = Field(None, description="备注")


class NewsCategoryEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="分类 ID")
    categoryName: str = Field(..., min_length=1, description="分类名称")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0停用 1启用")
    remark: Optional[str] = Field(None, description="备注")


class NewsCategoryDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除分类 ID 列表")


class NewsCategoryChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="分类 ID")
    status: int = Field(..., description="状态：0停用 1启用")


class NewsArticleListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    title: Optional[str] = Field(None, description="标题模糊搜索")
    categoryId: Optional[Union[str, int]] = Field(None, description="分类 ID")


class NewsArticleAddBody(BaseModel):
    categoryId: Union[str, int] = Field(..., description="分类 ID")
    title: str = Field(..., min_length=1, description="新闻标题")
    author: Optional[str] = Field(None, description="作者")
    newsType: int = Field(0, description="类型：0图文内容 1外部跳转")
    content: Optional[str] = Field(None, description="正文内容")
    redirectUrl: Optional[str] = Field(None, description="跳转链接")
    imageUrl: Optional[str] = Field(None, description="封面图 URL")
    isTop: int = Field(0, description="是否置顶：0否 1是")
    status: int = Field(1, description="状态：0下架 1发布")


class NewsArticleEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="文章 ID")
    categoryId: Union[str, int] = Field(..., description="分类 ID")
    title: str = Field(..., min_length=1, description="新闻标题")
    author: Optional[str] = Field(None, description="作者")
    newsType: int = Field(0, description="类型：0图文内容 1外部跳转")
    content: Optional[str] = Field(None, description="正文内容")
    redirectUrl: Optional[str] = Field(None, description="跳转链接")
    imageUrl: Optional[str] = Field(None, description="封面图 URL")
    isTop: int = Field(0, description="是否置顶：0否 1是")
    status: int = Field(1, description="状态：0下架 1发布")


class NewsArticleDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除文章 ID 列表")


class NewsArticleChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="文章 ID")
    status: int = Field(..., description="状态：0下架 1发布")


class FragmentCategoryListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    code: Optional[str] = Field(None, description="标识码模糊搜索")
    name: Optional[str] = Field(None, description="位置名称模糊搜索")


class FragmentCategoryAddBody(BaseModel):
    code: str = Field(..., min_length=1, description="标识码")
    name: str = Field(..., min_length=1, description="位置名称")
    remark: Optional[str] = Field(None, description="备注")


class FragmentCategoryEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="位置 ID")
    code: str = Field(..., min_length=1, description="标识码")
    name: str = Field(..., min_length=1, description="位置名称")
    remark: Optional[str] = Field(None, description="备注")


class FragmentCategoryDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除位置 ID 列表")


class FragmentContentListBody(BaseModel):
    pageNum: int = Field(1, ge=1, description="当前页码")
    pageSize: int = Field(10, ge=1, le=200, description="每页条数")
    categoryId: Optional[Union[str, int]] = Field(None, description="碎片位置 ID，筛选")
    title: Optional[str] = Field(None, description="标题模糊搜索")


class FragmentContentAddBody(BaseModel):
    categoryId: Union[str, int] = Field(..., description="碎片位置 ID")
    title: str = Field(..., min_length=1, description="标题")
    imageUrl: Optional[str] = Field(None, description="图片链接")
    linkUrl: Optional[str] = Field(None, description="跳转链接")
    content: Optional[str] = Field(None, description="文本内容")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0下线 1上线")


class FragmentContentEditBody(BaseModel):
    id: Union[str, int] = Field(..., description="内容 ID")
    title: str = Field(..., min_length=1, description="标题")
    imageUrl: Optional[str] = Field(None, description="图片链接")
    linkUrl: Optional[str] = Field(None, description="跳转链接")
    content: Optional[str] = Field(None, description="文本内容")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态：0下线 1上线")


class FragmentContentDeleteBody(BaseModel):
    id: List[Union[str, int]] = Field(..., min_length=1, description="待删除内容 ID 列表")


class FragmentContentChangeStatusBody(BaseModel):
    id: Union[str, int] = Field(..., description="内容 ID")
    status: int = Field(..., description="状态：0下线 1上线")
