import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";
import { ResPage } from "@/api/interface";

export interface NewsCategoryRow {
  id: string;
  categoryName: string;
  sort: number;
  status: number;
  remark: string;
  createTime: string;
}

export interface NewsCategoryOption {
  label: string;
  value: string;
}

export interface NewsArticleRow {
  id: string;
  categoryId: string;
  categoryName: string;
  title: string;
  author: string;
  newsType: number;
  content: string;
  redirectUrl: string;
  imageUrl: string;
  isTop: number;
  status: number;
  createTime: string;
}

export const getNewsCategoryList = (params: { pageNum: number; pageSize: number; categoryName?: string }) => {
  return http.post<ResPage<NewsCategoryRow>>(PORT1 + `/biz/newsCategory/list`, params);
};

export const getAllNewsCategory = async () => {
  const res = await http.get<{ id: string; categoryName: string }[]>(PORT1 + `/biz/newsCategory/all`, {}, { loading: false });
  const raw = Array.isArray(res.data) ? res.data : [];
  const data: NewsCategoryOption[] = raw.map(item => ({
    value: String(item.id),
    label: item.categoryName
  }));
  return { ...res, data };
};

export const addNewsCategory = (params: { categoryName: string; sort?: number; status?: number; remark?: string }) => {
  return http.post(PORT1 + `/biz/newsCategory/add`, params);
};

export const editNewsCategory = (params: {
  id: string;
  categoryName: string;
  sort?: number;
  status?: number;
  remark?: string;
}) => {
  return http.post(PORT1 + `/biz/newsCategory/edit`, params);
};

export const deleteNewsCategory = (params: { id: string[] }) => {
  return http.post(PORT1 + `/biz/newsCategory/delete`, params);
};

export const changeNewsCategoryStatus = (params: { id: string; status: number }) => {
  return http.post(PORT1 + `/biz/newsCategory/changeStatus`, params);
};

export const getNewsArticleList = (params: { pageNum: number; pageSize: number; title?: string; categoryId?: string }) => {
  return http.post<ResPage<NewsArticleRow>>(PORT1 + `/biz/newsArticle/list`, params);
};

export const addNewsArticle = (params: {
  categoryId: string;
  title: string;
  author?: string;
  newsType?: number;
  content?: string;
  redirectUrl?: string;
  imageUrl?: string;
  isTop?: number;
  status?: number;
}) => {
  return http.post(PORT1 + `/biz/newsArticle/add`, params);
};

export const editNewsArticle = (params: {
  id: string;
  categoryId: string;
  title: string;
  author?: string;
  newsType?: number;
  content?: string;
  redirectUrl?: string;
  imageUrl?: string;
  isTop?: number;
  status?: number;
}) => {
  return http.post(PORT1 + `/biz/newsArticle/edit`, params);
};

export const deleteNewsArticle = (params: { id: string[] }) => {
  return http.post(PORT1 + `/biz/newsArticle/delete`, params);
};

export const changeNewsArticleStatus = (params: { id: string; status: number }) => {
  return http.post(PORT1 + `/biz/newsArticle/changeStatus`, params);
};
