import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";

/** 与后端 build_menu_tree_all 节点一致（含 children） */
export interface MenuTreeNode {
  id: number;
  label: string;
  menuType: string;
  parentId: number | null;
  path: string;
  name: string;
  component: string;
  permission?: string;
  meta: { icon?: string; title?: string; [k: string]: unknown };
  sort?: number;
  remark?: string;
  children?: MenuTreeNode[];
}

/** 菜单管理：全量树（含停用） */
export const getMenuManageTree = () => {
  return http.get<MenuTreeNode[]>(PORT1 + `/menu/manage_tree`);
};

export const addMenu = (params: {
  parentId?: number | null;
  menuType: string;
  name: string;
  title: string;
  path?: string;
  component?: string;
  icon?: string;
  permission?: string;
  sort?: number;
  remark?: string;
}) => {
  return http.post(PORT1 + `/menu/add`, params);
};

export const editMenu = (params: {
  id: string | number;
  parentId?: number | null;
  menuType?: string;
  name?: string;
  title?: string;
  path?: string;
  component?: string;
  icon?: string;
  permission?: string;
  sort?: number;
  remark?: string;
  status?: boolean;
}) => {
  return http.post(PORT1 + `/menu/edit`, params);
};

export const deleteMenu = (params: { id: string | number }) => {
  return http.post(PORT1 + `/menu/delete`, params);
};
