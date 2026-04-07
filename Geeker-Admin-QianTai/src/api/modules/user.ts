import { ResPage, User } from "@/api/interface/index";
import { PORT1 } from "@/api/config/servicePort";
import http from "@/api";

/**
 * @name 用户管理模块
 * 列表接口：FastAPI 同路径注册在 PORT1（/geeker/user/list）与 /api/user/list
 */
// 获取用户列表
export const getUserList = (params: User.ReqUserParams) => {
  return http.post<ResPage<User.ResUserList>>(PORT1 + `/user/list`, params);
};

// 获取树形用户列表
export const getUserTreeList = (params: User.ReqUserParams) => {
  return http.post<ResPage<User.ResUserList>>(PORT1 + `/user/tree/list`, params);
};

/**
 * 新增用户（后端 bcrypt 存密码；业务上需传 username、password）
 * 参数使用 any 以兼容 ProTable 演示里 UserDrawer 的旧结构
 */
export const addUser = (params: any) => {
  return http.post(PORT1 + `/user/add`, params);
};

// 导入用户数据
export const importUser = (params: FormData) => {
  return http.post(PORT1 + `/user/import`, params);
};

// 兼容历史命名
export const BatchAddUser = importUser;

// 编辑用户（不改密码）
export const editUser = (params: {
  id: string;
  username?: string;
  nickname?: string;
  email?: string;
  phone?: string;
  gender?: string;
  roleIds?: number[];
}) => {
  return http.post(PORT1 + `/user/edit`, params);
};

// 删除用户
export const deleteUser = (params: { id: string[] }) => {
  return http.post(PORT1 + `/user/delete`, params);
};

// 切换用户状态（1 启用 / 0 禁用）
export const changeUserStatus = (params: { id: string; status: number }) => {
  return http.post(PORT1 + `/user/changeStatus`, params);
};

// 重置用户密码
export const resetUserPassWord = (params: { id: string }) => {
  return http.post(PORT1 + `/user/rest_password`, params);
};

// 导出用户数据
export const exportUser = (params: User.ReqUserParams) => {
  return http.download(PORT1 + `/user/export`, params);
};

// 兼容历史命名
export const exportUserInfo = exportUser;

// 下载用户导入模板
export const exportUserTemplate = () => {
  return http.download(PORT1 + `/user/template`, {});
};

// 获取用户状态字典
export const getUserStatus = () => {
  return http.get<User.ResStatus[]>(PORT1 + `/user/status`);
};

// 获取用户性别字典
export const getUserGender = () => {
  return http.get<User.ResGender[]>(PORT1 + `/user/gender`);
};

// 获取用户部门列表
export const getUserDepartment = () => {
  return http.get<User.ResDepartment[]>(PORT1 + `/user/department`, {}, { cancel: false });
};

// 获取用户角色字典
export const getUserRole = () => {
  return http.get<User.ResRole[]>(PORT1 + `/user/role`);
};
