<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
      <template #tableHeader="{ selectedListIds }">
        <el-button v-auth="'fragmentCategory:add'" type="primary" :icon="CirclePlus" @click="openAdd">新增位置</el-button>
        <el-button
          v-auth="'fragmentCategory:delete'"
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
        <el-button v-auth="'fragmentCategory:add'" type="primary" link :icon="CirclePlus" @click="openAdd">新增</el-button>
        <el-button v-auth="'fragmentCategory:edit'" type="primary" link :icon="EditPen" @click="openEdit(scope.row)">
          编辑
        </el-button>
        <el-button v-auth="'fragmentCategory:delete'" type="danger" link :icon="Delete" @click="deleteOne(scope.row)">
          删除
        </el-button>
        <el-button v-auth="'fragmentContent:add'" type="primary" link @click="openContent(scope.row)">内容管理</el-button>
      </template>
    </ProTable>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑碎片位置' : '新增碎片位置'"
      width="520px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="标识码" prop="code">
          <el-input v-model="form.code" placeholder="如 home_banner" clearable />
        </el-form-item>
        <el-form-item label="位置名称" prop="name">
          <el-input v-model="form.name" placeholder="如 首页轮播图" clearable />
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

    <FragmentContentDrawer
      v-model="contentDrawerVisible"
      :category-id="contentCategoryId"
      :category-code="contentCategoryCode"
      :category-name="contentCategoryName"
    />
  </div>
</template>

<script setup lang="tsx" name="fragmentManage">
import { reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import FragmentContentDrawer from "./FragmentContentDrawer.vue";
import {
  addFragmentCategory,
  deleteFragmentCategory,
  editFragmentCategory,
  getFragmentCategoryList,
  type FragmentCategoryRow
} from "@/api/modules/fragment";
import { useHandleData } from "@/hooks/useHandleData";

const proTable = ref<ProTableInstance>();
const dialogVisible = ref(false);
const isEdit = ref(false);
const formRef = ref<FormInstance>();

const contentDrawerVisible = ref(false);
const contentCategoryId = ref("");
const contentCategoryCode = ref("");
const contentCategoryName = ref("");

const form = reactive({
  id: "",
  code: "",
  name: "",
  remark: ""
});

const rules: FormRules = {
  code: [{ required: true, message: "请输入标识码", trigger: "blur" }],
  name: [{ required: true, message: "请输入位置名称", trigger: "blur" }]
};

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getFragmentCategoryList(JSON.parse(JSON.stringify(params)));

const openAdd = () => {
  isEdit.value = false;
  dialogVisible.value = true;
};

const openEdit = (row: FragmentCategoryRow) => {
  isEdit.value = true;
  form.id = row.id;
  form.code = row.code || "";
  form.name = row.name || "";
  form.remark = row.remark || "";
  dialogVisible.value = true;
};

const openContent = (row: FragmentCategoryRow) => {
  contentCategoryId.value = row.id;
  contentCategoryCode.value = row.code || "";
  contentCategoryName.value = row.name || "";
  contentDrawerVisible.value = true;
};

const resetForm = () => {
  form.id = "";
  form.code = "";
  form.name = "";
  form.remark = "";
  isEdit.value = false;
  formRef.value?.clearValidate();
};

const submitForm = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      if (isEdit.value) {
        const res = await editFragmentCategory({
          id: form.id,
          code: form.code.trim(),
          name: form.name.trim(),
          remark: form.remark || undefined
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addFragmentCategory({
          code: form.code.trim(),
          name: form.name.trim(),
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

const deleteOne = async (row: FragmentCategoryRow) => {
  await useHandleData(deleteFragmentCategory, { id: [row.id] }, `删除【${row.name}】位置`);
  proTable.value?.getTableList();
};

const batchDelete = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteFragmentCategory, { id: ids }, "删除所选位置");
  proTable.value?.clearSelection();
  proTable.value?.getTableList();
};

const columns = reactive<ColumnProps<FragmentCategoryRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 56 },
  {
    prop: "code",
    label: "标识码",
    minWidth: 140,
    search: { el: "input" }
  },
  {
    prop: "name",
    label: "位置名称",
    minWidth: 160,
    search: { el: "input" }
  },
  {
    prop: "remark",
    label: "备注",
    minWidth: 200
  },
  {
    prop: "createTime",
    label: "创建时间",
    width: 170
  },
  { prop: "operation", label: "操作", fixed: "right", width: 320 }
]);
</script>
