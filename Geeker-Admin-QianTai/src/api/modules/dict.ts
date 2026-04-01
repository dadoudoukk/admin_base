import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";
import { ResPage } from "@/api/interface";

/** 后端字典项（/dict/data 返回） */
export interface DictDataItem {
  dictLabel: string;
  dictValue: string;
}

/** ProTable / el-select 通用 { label, value } */
export interface DictOption {
  label: string;
  value: string;
}

export interface DictTypeRow {
  id: string;
  dictName: string;
  dictCode: string;
  status: number;
  remark: string;
  createTime: string;
  updateTime: string;
}

export interface DictDataRow {
  id: string;
  dictCode: string;
  dictLabel: string;
  dictValue: string;
  sort: number;
  status: boolean;
  remark: string;
  createdAt: string;
  updatedAt: string;
}

/**
 * 按字典编码拉取选项，并映射为 ProTable 默认识别的 label / value（value 统一为字符串，与后端 gender 一致）
 */
export const getDictByCode = async (dictCode: string) => {
  const res = await http.get<DictDataItem[]>(PORT1 + `/dict/data/${encodeURIComponent(dictCode)}`, {}, { loading: false });
  const raw = Array.isArray(res.data) ? res.data : [];
  const data: DictOption[] = raw.map(item => ({
    label: item.dictLabel,
    value: String(item.dictValue)
  }));
  return { ...res, data };
};

export const getDictTypeList = (params: { pageNum: number; pageSize: number; dictName?: string; dictCode?: string }) => {
  return http.post<ResPage<DictTypeRow>>(PORT1 + `/dict/type/list`, params);
};

export const addDictType = (params: { dictName: string; dictCode: string; status?: boolean; remark?: string }) => {
  return http.post(PORT1 + `/dict/type/add`, params);
};

export const editDictType = (params: { id: string; dictName: string; dictCode: string; status?: boolean; remark?: string }) => {
  return http.post(PORT1 + `/dict/type/edit`, params);
};

export const deleteDictType = (params: { id: string[] }) => {
  return http.post(PORT1 + `/dict/type/delete`, params);
};

export const changeDictTypeStatus = (params: { id: string; status: boolean | number }) => {
  return http.post(PORT1 + `/dict/type/changeStatus`, params);
};

export const getDictDataList = (params: {
  pageNum: number;
  pageSize: number;
  dictCode: string;
  dictLabel?: string;
  dictValue?: string;
}) => {
  return http.post<ResPage<DictDataRow>>(PORT1 + `/dict/data/list`, params);
};

export const addDictData = (params: {
  dictCode: string;
  dictLabel: string;
  dictValue: string;
  sort?: number;
  status?: boolean;
  remark?: string;
}) => {
  return http.post(PORT1 + `/dict/data/add`, params);
};

export const editDictData = (params: {
  id: string;
  dictCode: string;
  dictLabel: string;
  dictValue: string;
  sort?: number;
  status?: boolean;
  remark?: string;
}) => {
  return http.post(PORT1 + `/dict/data/edit`, params);
};

export const deleteDictData = (params: { id: string[] }) => {
  return http.post(PORT1 + `/dict/data/delete`, params);
};

export const changeDictDataStatus = (params: { id: string; status: boolean | number }) => {
  return http.post(PORT1 + `/dict/data/changeStatus`, params);
};
