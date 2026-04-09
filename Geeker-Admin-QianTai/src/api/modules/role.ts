import { ResPage, Role } from "@/api/interface/index";
import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";

/** 角色列表项（与后端 _role_row 对齐） */
export interface RoleRow {
  id: string;
  roleName: string;
  roleCode: string;
  remark: string;
  data_scope: number;
  custom_dept_ids: number[];
  status: number;
  createTime: string;
}

export interface RoleOption {
  id: number;
  roleName: string;
}

export interface ReqRoleList {
  pageNum: number;
  pageSize: number;
  roleName?: string;
  roleCode?: string;
}

/**
 * @name 角色管理（与 FastAPI /api/role/* 对齐）
 */
export const getRoleList = (params: ReqRoleList) => {
  return http.post<ResPage<RoleRow>>(PORT1 + `/role/list`, params);
};

export const getAllRoleList = () => {
  return http.get<RoleOption[]>(PORT1 + `/role/all`);
};

export const addRole = (params: Role.ReqRoleSubmit) => {
  return http.post(PORT1 + `/role/add`, params);
};

export const editRole = (params: Role.ReqRoleSubmit) => {
  return http.post(PORT1 + `/role/edit`, params);
};

export const deleteRole = (params: { id: string[] }) => {
  return http.post(PORT1 + `/role/delete`, params);
};

/** 全部菜单树（权限分配） */
export const getMenuAllTree = () => {
  return http.get<unknown[]>(PORT1 + `/menu/all_tree`);
};

/** 角色已分配的菜单 ID */
export const getRoleMenuIds = (params: { roleId: string | number }) => {
  return http.post<number[]>(PORT1 + `/role/getMenuIds`, params);
};

/** 保存角色菜单关联 */
export const assignRoleMenus = (params: { roleId: string | number; menuIds: number[] }) => {
  return http.post(PORT1 + `/role/assignMenu`, params);
};

/** 部门树（数据权限-自定义部门） */
export const getRoleDeptTree = () => {
  return http.get<Role.ResDeptTreeNode[]>(PORT1 + `/role/deptTree`);
};
