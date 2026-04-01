<template>
  <div class="table-box" v-loading="loading">
    <ProTable
      ref="proTable"
      title="菜单列表"
      row-key="id"
      :indent="20"
      :columns="columns"
      :data="tableData"
      :pagination="false"
      :request-auto="false"
      :tree-props="{ children: 'children' }"
      default-expand-all
      :tool-button="false"
    >
      <template #tableHeader>
        <el-button type="primary" :icon="CirclePlus" @click="openAddRoot">新增菜单</el-button>
        <el-button @click="loadTree">刷新</el-button>
      </template>
      <template #icon="scope">
        <span>{{ scope.row.meta?.icon || "—" }}</span>
      </template>
      <template #operation="scope">
        <el-button type="primary" link :icon="CirclePlus" @click="openAddChild(scope.row)">新增下级</el-button>
        <el-button type="primary" link :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
        <el-button type="danger" link :icon="Delete" @click="removeRow(scope.row)">删除</el-button>
      </template>
    </ProTable>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px" destroy-on-close @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="108px">
        <el-form-item label="父级 ID" prop="parentId">
          <el-input-number
            v-model="form.parentId"
            :min="0"
            :step="1"
            controls-position="right"
            placeholder="0 表示根"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="类型" prop="menuType">
          <el-select v-model="form.menuType" placeholder="请选择" style="width: 100%">
            <el-option label="目录 CATALOG" value="CATALOG" />
            <el-option label="菜单 MENU" value="MENU" />
            <el-option label="按钮 BUTTON" value="BUTTON" />
          </el-select>
        </el-form-item>
        <el-form-item label="路由 name" prop="name">
          <el-input v-model="form.name" placeholder="如 home_index" clearable />
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" placeholder="显示名称" clearable />
        </el-form-item>
        <el-form-item label="路径 path" prop="path">
          <el-input v-model="form.path" placeholder="如 /home/index" clearable />
        </el-form-item>
        <el-form-item label="组件" prop="component">
          <el-input v-model="form.component" placeholder="如 /home/index" clearable />
        </el-form-item>
        <el-form-item label="图标" prop="icon">
          <el-input v-model="form.icon" placeholder="Element 图标名，如 HomeFilled" clearable />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" controls-position="right" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="form.remark" type="textarea" :rows="2" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts" name="menuMange">
import { onMounted, reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps } from "@/components/ProTable/interface";
import { getMenuManageTree, addMenu, editMenu, deleteMenu, type MenuTreeNode } from "@/api/modules/menu";
import { useHandleData } from "@/hooks/useHandleData";

const loading = ref(false);
const tableData = ref<MenuTreeNode[]>([]);
const dialogVisible = ref(false);
const dialogTitle = ref("新增菜单");
const formMode = ref<"add" | "edit" | "child">("add");
const formRef = ref<FormInstance>();
const editingId = ref<string | number | null>(null);

const form = reactive({
  parentId: 0,
  menuType: "MENU",
  name: "",
  title: "",
  path: "",
  component: "",
  icon: "",
  sort: 0,
  remark: ""
});

const rules: FormRules = {
  menuType: [{ required: true, message: "请选择类型", trigger: "change" }],
  name: [{ required: true, message: "请输入路由 name", trigger: "blur" }],
  title: [{ required: true, message: "请输入标题", trigger: "blur" }]
};

const columns: ColumnProps[] = [
  { prop: "label", label: "菜单名称", align: "left", width: 200 },
  { prop: "menuType", label: "类型", width: 110 },
  { prop: "name", label: "name", width: 140 },
  { prop: "path", label: "路径", minWidth: 160 },
  { prop: "component", label: "组件", minWidth: 180 },
  { prop: "icon", label: "图标", width: 120 },
  { prop: "operation", label: "操作", width: 280, fixed: "right" }
];

const loadTree = async () => {
  loading.value = true;
  try {
    const res = await getMenuManageTree();
    tableData.value = (res as any).data ?? [];
  } finally {
    loading.value = false;
  }
};

onMounted(() => {
  loadTree();
});

const resetForm = () => {
  editingId.value = null;
  form.parentId = 0;
  form.menuType = "MENU";
  form.name = "";
  form.title = "";
  form.path = "";
  form.component = "";
  form.icon = "";
  form.sort = 0;
  form.remark = "";
  formRef.value?.clearValidate();
};

const openAddRoot = () => {
  formMode.value = "add";
  dialogTitle.value = "新增菜单";
  resetForm();
  form.parentId = 0;
  dialogVisible.value = true;
};

const openAddChild = (row: MenuTreeNode) => {
  formMode.value = "child";
  dialogTitle.value = "新增下级菜单";
  resetForm();
  form.parentId = row.id;
  dialogVisible.value = true;
};

const openEdit = (row: MenuTreeNode) => {
  formMode.value = "edit";
  dialogTitle.value = "编辑菜单";
  editingId.value = row.id;
  form.parentId = row.parentId ?? 0;
  form.menuType = row.menuType || "MENU";
  form.name = row.name;
  form.title = row.label;
  form.path = row.path || "";
  form.component = row.component || "";
  form.icon = row.meta?.icon || "";
  form.sort = row.sort ?? 0;
  form.remark = row.remark || "";
  dialogVisible.value = true;
};

const submitForm = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    const parentPayload = form.parentId === 0 ? undefined : form.parentId;
    try {
      if (formMode.value === "edit" && editingId.value != null) {
        const res = await editMenu({
          id: editingId.value,
          parentId: parentPayload ?? 0,
          menuType: form.menuType,
          name: form.name.trim(),
          title: form.title.trim(),
          path: form.path || undefined,
          component: form.component || undefined,
          icon: form.icon || undefined,
          sort: form.sort,
          remark: form.remark || undefined
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addMenu({
          parentId: parentPayload,
          menuType: form.menuType,
          name: form.name.trim(),
          title: form.title.trim(),
          path: form.path || undefined,
          component: form.component || undefined,
          icon: form.icon || undefined,
          sort: form.sort,
          remark: form.remark || undefined
        });
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      dialogVisible.value = false;
      await loadTree();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const removeRow = async (row: MenuTreeNode) => {
  await useHandleData(deleteMenu, { id: row.id }, `删除菜单【${row.label}】`);
  await loadTree();
};
</script>
