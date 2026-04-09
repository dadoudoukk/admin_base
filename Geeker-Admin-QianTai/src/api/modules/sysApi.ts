import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";
import type { ResPage } from "@/api/interface";

export interface SysApiRow {
  id: string;
  apiPath: string;
  apiMethod: string;
  apiName: string;
  apiModule: string;
  status: number;
  authRequired: number;
  logRequired: number;
  rateLimit: number;
  remark: string;
  createTime: string;
  updateTime: string;
}

export interface ReqSysApiList {
  pageNum: number;
  pageSize: number;
  apiPath?: string;
  apiMethod?: string;
  apiModule?: string;
}

export interface ReqSysApiEdit {
  id: string | number;
  api_name?: string;
  api_module?: string;
  status?: boolean;
  auth_required?: boolean;
  log_required?: boolean;
  rate_limit?: number;
  remark?: string;
}

export interface ReqSysApiChangeStatus {
  id: string | number;
  field: "status" | "auth_required" | "log_required";
  value: boolean | number;
}

export interface ApiModuleOption {
  label: string;
  value: string;
}

export const getSysApiModuleOptions = () => {
  return http.get<ApiModuleOption[]>(PORT1 + `/sys/api/module_options`);
};

export const syncSysApi = () => {
  return http.post(PORT1 + `/sys/api/sync`);
};

export const getSysApiList = (params: ReqSysApiList) => {
  return http.post<ResPage<SysApiRow>>(PORT1 + `/sys/api/list`, params);
};

export const editSysApi = (params: ReqSysApiEdit) => {
  return http.post(PORT1 + `/sys/api/edit`, params);
};

export const changeSysApiStatus = (params: ReqSysApiChangeStatus) => {
  return http.post(PORT1 + `/sys/api/changeStatus`, params);
};
