<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
      <template #tableHeader="{ selectedListIds }">
        <el-button v-auth="'user:add'" type="primary" :icon="CirclePlus" @click="openAdd">新增用户</el-button>
        <el-button
          v-auth="'user:delete'"
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
        <el-button v-auth="'user:edit'" type="primary" link :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
        <el-button v-auth="'user:delete'" type="danger" link :icon="Delete" @click="deleteAccount(scope.row)">删除</el-button>
      </template>
    </ProTable>

    <el-dialog
      v-model="addVisible"
      :title="isEdit ? '编辑用户' : '新增用户'"
      width="480px"
      destroy-on-close
      @closed="resetAddForm"
    >
      <el-form ref="addFormRef" :model="addForm" :rules="formRules" label-width="88px">
        <el-form-item label="账号" prop="username">
          <el-input v-model="addForm.username" placeholder="登录账号" autocomplete="off" clearable />
        </el-form-item>
        <el-form-item v-if="!isEdit" label="密码" prop="password">
          <el-input
            v-model="addForm.password"
            type="password"
            placeholder="登录密码"
            show-password
            autocomplete="new-password"
            clearable
          />
        </el-form-item>
        <el-form-item label="昵称" prop="nickname">
          <el-input v-model="addForm.nickname" placeholder="选填" clearable />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="addForm.email" placeholder="选填" clearable />
        </el-form-item>
        <el-form-item label="手机" prop="phone">
          <el-input v-model="addForm.phone" placeholder="选填" clearable />
        </el-form-item>
        <el-form-item label="性别" prop="gender">
          <el-select v-model="addForm.gender" placeholder="请选择性别" clearable style="width: 100%">
            <el-option v-for="item in sexDictOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="roleIds">
          <el-select v-model="addForm.roleIds" multiple placeholder="请选择角色" clearable style="width: 100%">
            <el-option v-for="item in roleOptions" :key="item.id" :label="item.roleName" :value="item.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="tsx" name="accountManage">
import { computed, onMounted, reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import { User } from "@/api/interface";
import { getUserList, addUser, deleteUser, editUser, changeUserStatus } from "@/api/modules/user";
import { getDictByCode, type DictOption } from "@/api/modules/dict";
import { getAllRoleList, type RoleOption } from "@/api/modules/role";
import { useHandleData } from "@/hooks/useHandleData";

const proTable = ref<ProTableInstance>();
const addVisible = ref(false);
const isEdit = ref(false);
const addFormRef = ref<FormInstance>();
const sexDictOptions = ref<DictOption[]>([]);
const roleOptions = ref<RoleOption[]>([]);

const addForm = reactive({
  id: "",
  username: "",
  password: "",
  nickname: "",
  email: "",
  phone: "",
  gender: "3",
  roleIds: [] as number[]
});

onMounted(async () => {
  const [sexRes, roleRes] = await Promise.all([getDictByCode("sys_user_sex"), getAllRoleList()]);
  sexDictOptions.value = sexRes.data;
  roleOptions.value = roleRes.data || [];
});

const formRules = computed<FormRules>(() => ({
  username: [{ required: true, message: "请输入账号", trigger: "blur" }],
  password: isEdit.value ? [] : [{ required: true, message: "请输入密码", trigger: "blur" }]
}));

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getUserList(JSON.parse(JSON.stringify(params)));

const openAdd = () => {
  isEdit.value = false;
  addVisible.value = true;
};

const openEdit = (row: User.ResUserList) => {
  isEdit.value = true;
  addForm.id = String(row.id);
  addForm.username = row.username;
  addForm.password = "";
  addForm.nickname = (row as User.ResUserList & { nickname?: string }).nickname || "";
  addForm.email = row.email || "";
  addForm.phone = (row as User.ResUserList & { phone?: string }).phone || "";
  addForm.gender = row.gender != null && row.gender !== "" ? String(row.gender) : "3";
  addForm.roleIds = Array.isArray(row.roleIds) ? row.roleIds.map(id => Number(id)) : [];
  addVisible.value = true;
};

const resetAddForm = () => {
  addForm.id = "";
  addForm.username = "";
  addForm.password = "";
  addForm.nickname = "";
  addForm.email = "";
  addForm.phone = "";
  addForm.gender = "3";
  addForm.roleIds = [];
  isEdit.value = false;
  addFormRef.value?.clearValidate();
};

const submitForm = () => {
  addFormRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      if (isEdit.value) {
        const res = await editUser({
          id: addForm.id,
          username: addForm.username.trim(),
          nickname: addForm.nickname,
          email: addForm.email,
          phone: addForm.phone,
          gender: addForm.gender || "3",
          roleIds: addForm.roleIds
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addUser({
          username: addForm.username.trim(),
          password: addForm.password,
          nickname: addForm.nickname || undefined,
          email: addForm.email || undefined,
          phone: addForm.phone || undefined,
          gender: addForm.gender || "3",
          roleIds: addForm.roleIds
        });
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      addVisible.value = false;
      proTable.value?.getTableList();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const handleStatusBeforeChange = (row: User.ResUserList) => {
  const next = row.status === 1 ? 0 : 1;
  return changeUserStatus({ id: row.id, status: next })
    .then(res => {
      ElMessage.success({ message: res.msg || "状态修改成功" });
      proTable.value?.getTableList();
      return true;
    })
    .catch(() => false);
};

const deleteAccount = async (params: User.ResUserList) => {
  await useHandleData(deleteUser, { id: [params.id] }, `删除【${params.username}】用户`);
  proTable.value?.getTableList();
};

const batchDelete = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteUser, { id: ids }, "删除所选用户信息");
  proTable.value?.clearSelection();
  proTable.value?.getTableList();
};

const columns = reactive<ColumnProps<User.ResUserList>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 60 },
  {
    prop: "username",
    label: "账号",
    search: { el: "input" }
  },
  {
    prop: "gender",
    label: "性别",
    width: 100,
    enum: sexDictOptions,
    fieldNames: { label: "label", value: "value" },
    search: { el: "select" },
    render: scope => {
      const gv = String(scope.row.gender ?? "");
      const item = sexDictOptions.value.find(opt => String(opt.value) === gv);
      if (!item) return "--";
      return <el-tag size="small">{item.label}</el-tag>;
    }
  },
  {
    prop: "roleNames",
    label: "所属角色",
    minWidth: 220,
    isFilterEnum: false,
    render: scope => {
      const names = Array.isArray(scope.row.roleNames) ? scope.row.roleNames.filter(Boolean) : [];
      if (!names.length) return "--";
      return (
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
          {names.map((name: string) => (
            <el-tag key={name} size="small">
              {name}
            </el-tag>
          ))}
        </div>
      );
    }
  },
  {
    prop: "status",
    label: "状态",
    width: 100,
    render: scope => (
      <el-switch
        model-value={scope.row.status}
        active-value={1}
        inactive-value={0}
        beforeChange={() => handleStatusBeforeChange(scope.row)}
      />
    )
  },
  {
    prop: "createTime",
    label: "创建时间",
    width: 180
  },
  {
    prop: "email",
    label: "邮箱",
    width: 200
  },
  { prop: "operation", label: "操作", fixed: "right", width: 180 }
]);
</script>
