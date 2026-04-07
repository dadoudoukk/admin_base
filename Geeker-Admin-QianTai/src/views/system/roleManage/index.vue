<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
      <template #tableHeader="{ selectedListIds }">
        <el-button v-auth="'role:add'" type="primary" :icon="CirclePlus" @click="openAdd">新增角色</el-button>
        <el-button
          v-auth="'role:delete'"
          type="danger"
          :icon="Delete"
          plain
          :disabled="!selectedListIds?.length"
          @click="batchDelete(selectedListIds)"
        >
          批量删除
        </el-button>
      </template>
      <template #operation="scope">
        <el-button v-auth="'role:edit'" type="primary" link :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
        <el-button v-auth="'role:auth'" type="primary" link :icon="Key" @click="openMenuAuth(scope.row)">菜单权限</el-button>
        <el-button v-auth="'role:delete'" type="danger" link :icon="Delete" @click="deleteOne(scope.row)">删除</el-button>
      </template>
    </ProTable>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑角色' : '新增角色'"
      width="480px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="角色名称" prop="roleName">
          <el-input v-model="form.roleName" placeholder="如：普通运营" clearable />
        </el-form-item>
        <el-form-item label="角色标识" prop="roleCode">
          <el-input
            v-model="form.roleCode"
            placeholder="如：operator"
            clearable
            :disabled="isEdit && form.roleCode === 'admin'"
          />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="3" placeholder="选填" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>

    <el-drawer v-model="authDrawerVisible" :title="authDrawerTitle" size="400px" destroy-on-close @closed="onAuthDrawerClosed">
      <div v-loading="authLoading" class="auth-drawer-body">
        <el-tree
          v-if="treeData.length"
          ref="treeRef"
          :data="treeData"
          node-key="id"
          show-checkbox
          default-expand-all
          :props="{ label: 'label', children: 'children' }"
        />
        <el-empty v-else-if="!authLoading" description="暂无菜单数据" />
      </div>
      <template #footer>
        <el-button @click="authDrawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="authSaving" @click="saveMenuAuth">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="tsx" name="roleManage">
import { nextTick, reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen, Key } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import type { ElTree } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import {
  getRoleList,
  addRole,
  editRole,
  deleteRole,
  getMenuAllTree,
  getRoleMenuIds,
  assignRoleMenus,
  type RoleRow
} from "@/api/modules/role";
import { useHandleData } from "@/hooks/useHandleData";

const proTable = ref<ProTableInstance>();
const dialogVisible = ref(false);
const isEdit = ref(false);
const formRef = ref<FormInstance>();
const form = reactive({
  id: "",
  roleName: "",
  roleCode: "",
  remark: ""
});

const authDrawerVisible = ref(false);
const authDrawerTitle = ref("菜单权限");
const authRoleId = ref("");
const authLoading = ref(false);
const authSaving = ref(false);
const treeData = ref<any[]>([]);
const treeRef = ref<InstanceType<typeof ElTree>>();

const rules: FormRules = {
  roleName: [{ required: true, message: "请输入角色名称", trigger: "blur" }],
  roleCode: [{ required: true, message: "请输入角色标识", trigger: "blur" }]
};

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getRoleList(JSON.parse(JSON.stringify(params)));

const openAdd = () => {
  isEdit.value = false;
  dialogVisible.value = true;
};

const openEdit = (row: RoleRow) => {
  isEdit.value = true;
  form.id = row.id;
  form.roleName = row.roleName;
  form.roleCode = row.roleCode;
  form.remark = row.remark || "";
  dialogVisible.value = true;
};

const resetForm = () => {
  form.id = "";
  form.roleName = "";
  form.roleCode = "";
  form.remark = "";
  isEdit.value = false;
  formRef.value?.clearValidate();
};

const submitForm = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      if (isEdit.value) {
        const res = await editRole({
          id: form.id,
          roleName: form.roleName.trim(),
          roleCode: form.roleCode.trim(),
          remark: form.remark
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addRole({
          roleName: form.roleName.trim(),
          roleCode: form.roleCode.trim(),
          remark: form.remark || undefined
        });
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      dialogVisible.value = false;
      proTable.value?.getTableList();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const openMenuAuth = async (row: RoleRow) => {
  authRoleId.value = row.id;
  authDrawerTitle.value = `菜单权限 — ${row.roleName}`;
  authDrawerVisible.value = true;
  authLoading.value = true;
  treeData.value = [];
  try {
    const [treeRes, idsRes] = await Promise.all([getMenuAllTree(), getRoleMenuIds({ roleId: row.id })]);
    treeData.value = (treeRes as any).data ?? [];
    await nextTick();
    const ids = ((idsRes as any).data ?? []) as number[];
    treeRef.value?.setCheckedKeys(ids, false);
  } catch {
    treeData.value = [];
  } finally {
    authLoading.value = false;
  }
};

const onAuthDrawerClosed = () => {
  authRoleId.value = "";
  treeData.value = [];
};

const saveMenuAuth = async () => {
  if (!authRoleId.value || !treeRef.value) return;
  const checked = treeRef.value.getCheckedKeys(false) as number[];
  const half = treeRef.value.getHalfCheckedKeys() as number[];
  const menuIds = [...new Set([...checked, ...half])];
  authSaving.value = true;
  try {
    const res = await assignRoleMenus({ roleId: authRoleId.value, menuIds });
    ElMessage.success({ message: res.msg || "权限分配成功" });
    authDrawerVisible.value = false;
  } catch {
    /* 全局拦截器已提示错误 */
  } finally {
    authSaving.value = false;
  }
};

const deleteOne = async (row: RoleRow) => {
  await useHandleData(deleteRole, { id: [row.id] }, `删除【${row.roleName}】角色`);
  proTable.value?.getTableList();
};

const batchDelete = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteRole, { id: ids }, "删除所选角色");
  proTable.value?.clearSelection();
  proTable.value?.getTableList();
};

const columns = reactive<ColumnProps<RoleRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 60 },
  {
    prop: "roleName",
    label: "角色名称",
    search: { el: "input" }
  },
  {
    prop: "roleCode",
    label: "角色标识",
    search: { el: "input" }
  },
  {
    prop: "remark",
    label: "备注",
    minWidth: 160
  },
  {
    prop: "createTime",
    label: "创建时间",
    width: 180
  },
  { prop: "operation", label: "操作", fixed: "right", width: 280 }
]);
</script>

<style scoped>
.auth-drawer-body {
  min-height: 200px;
}
</style>
