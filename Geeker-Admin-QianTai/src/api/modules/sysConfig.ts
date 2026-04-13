import http from "@/api";
import { PORT1 } from "@/api/config/servicePort";

/** 与后端 GET /sys_config/all 的 data 一致 */
export interface SysConfigAllPayload {
  list: Record<string, unknown>[];
  map: Record<string, unknown>;
}

export const getSysConfigAll = () => {
  return http.get<SysConfigAllPayload>(PORT1 + `/sys_config/all`, {}, { loading: false });
};

/** 免登录公开配置，data 为 { sys_app_name?, sys_logo? } */
export const getSysConfigPublic = () => {
  return http.get<Record<string, string | null | undefined>>(PORT1 + `/sys_config/public`, {}, { loading: false, cancel: false });
};

export const updateSysConfigBatch = (params: any) => {
  return http.put<unknown>(PORT1 + `/sys_config/update`, params, { loading: true });
};
