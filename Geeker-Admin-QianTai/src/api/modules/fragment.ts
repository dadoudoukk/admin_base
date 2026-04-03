import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";
import { ResPage } from "@/api/interface";

export interface FragmentCategoryRow {
  id: string;
  code: string;
  name: string;
  remark: string;
  createTime: string;
}

export interface FragmentContentRow {
  id: string;
  categoryId: string;
  title: string;
  imageUrl: string;
  linkUrl: string;
  content: string;
  sort: number;
  status: number;
  createTime: string;
}

export const getFragmentCategoryList = (params: { pageNum: number; pageSize: number; code?: string; name?: string }) => {
  return http.post<ResPage<FragmentCategoryRow>>(PORT1 + `/biz/fragment/category/list`, params);
};

export const addFragmentCategory = (params: { code: string; name: string; remark?: string }) => {
  return http.post(PORT1 + `/biz/fragment/category/add`, params);
};

export const editFragmentCategory = (params: { id: string; code: string; name: string; remark?: string }) => {
  return http.post(PORT1 + `/biz/fragment/category/edit`, params);
};

export const deleteFragmentCategory = (params: { id: string[] }) => {
  return http.post(PORT1 + `/biz/fragment/category/delete`, params);
};

export const getFragmentContentList = (params: { pageNum: number; pageSize: number; categoryId?: string; title?: string }) => {
  return http.post<ResPage<FragmentContentRow>>(PORT1 + `/biz/fragment/content/list`, params);
};

export const addFragmentContent = (params: {
  categoryId: string;
  title: string;
  imageUrl?: string;
  linkUrl?: string;
  content?: string;
  sort?: number;
  status?: number;
}) => {
  return http.post(PORT1 + `/biz/fragment/content/add`, params);
};

export const editFragmentContent = (params: {
  id: string;
  title: string;
  imageUrl?: string;
  linkUrl?: string;
  content?: string;
  sort?: number;
  status?: number;
}) => {
  return http.post(PORT1 + `/biz/fragment/content/edit`, params);
};

export const deleteFragmentContent = (params: { id: string[] }) => {
  return http.post(PORT1 + `/biz/fragment/content/delete`, params);
};

export const changeFragmentContentStatus = (params: { id: string; status: number }) => {
  return http.post(PORT1 + `/biz/fragment/content/changeStatus`, params);
};
