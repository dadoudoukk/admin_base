import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";
import { ResPage } from "@/api/interface";

export interface SystemOperLogRow {
  id: string;
  userName: string;
  requestMethod: string;
  requestUrl: string;
  requestIp: string;
  executeTime: number;
  status: number;
  errorMsg: string;
  requestParam: string;
  createTime: string;
}

export const getSystemLogList = (params: { pageNum: number; pageSize: number; userName?: string; requestMethod?: string }) => {
  return http.post<ResPage<SystemOperLogRow>>(PORT1 + `/sys/log/list`, params);
};

// 导出系统日志
export const exportSystemLog = (params: { userName?: string; requestMethod?: string }) => {
  return http.download(PORT1 + `/sys/log/export`, params);
};
