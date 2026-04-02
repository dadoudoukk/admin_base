<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
      <template #tableHeader="{ selectedListIds }">
        <el-button type="primary" :icon="CirclePlus" @click="openAdd">新增分类</el-button>
        <el-button type="danger" :icon="Delete" plain :disabled="!selectedListIds?.length" @click="batchDelete(selectedListIds)">
          批量删除
        </el-button>
      </template>
      <template #operation="scope">
        <el-button type="primary" link :icon="EditPen" @click="openEdit(scope.row)">编辑</el-button>
        <el-button type="danger" link :icon="Delete" @click="deleteOne(scope.row)">删除</el-button>
      </template>
    </ProTable>

    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑分类' : '新增分类'"
      width="520px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="分类名称" prop="categoryName">
          <el-input v-model="form.categoryName" placeholder="如：公司新闻" clearable />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="form.sort" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
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
  </div>
</template>

<script setup lang="tsx" name="newsCategory">
import { reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import {
  addNewsCategory,
  changeNewsCategoryStatus,
  deleteNewsCategory,
  editNewsCategory,
  getNewsCategoryList,
  type NewsCategoryRow
} from "@/api/modules/news";
import { useHandleData } from "@/hooks/useHandleData";

const proTable = ref<ProTableInstance>();
const dialogVisible = ref(false);
const isEdit = ref(false);
const formRef = ref<FormInstance>();

const form = reactive({
  id: "",
  categoryName: "",
  sort: 0,
  status: 1,
  remark: ""
});

const rules: FormRules = {
  categoryName: [{ required: true, message: "请输入分类名称", trigger: "blur" }]
};

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getNewsCategoryList(JSON.parse(JSON.stringify(params)));

const openAdd = () => {
  isEdit.value = false;
  dialogVisible.value = true;
};

const openEdit = (row: NewsCategoryRow) => {
  isEdit.value = true;
  form.id = row.id;
  form.categoryName = row.categoryName;
  form.sort = Number(row.sort || 0);
  form.status = row.status === 1 ? 1 : 0;
  form.remark = row.remark || "";
  dialogVisible.value = true;
};

const resetForm = () => {
  form.id = "";
  form.categoryName = "";
  form.sort = 0;
  form.status = 1;
  form.remark = "";
  isEdit.value = false;
  formRef.value?.clearValidate();
};

const submitForm = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      if (isEdit.value) {
        const res = await editNewsCategory({
          id: form.id,
          categoryName: form.categoryName.trim(),
          sort: form.sort,
          status: form.status,
          remark: form.remark || undefined
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addNewsCategory({
          categoryName: form.categoryName.trim(),
          sort: form.sort,
          status: form.status,
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

const deleteOne = async (row: NewsCategoryRow) => {
  await useHandleData(deleteNewsCategory, { id: [row.id] }, `删除【${row.categoryName}】分类`);
  proTable.value?.getTableList();
};

const batchDelete = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteNewsCategory, { id: ids }, "删除所选分类");
  proTable.value?.clearSelection();
  proTable.value?.getTableList();
};

const handleStatusBeforeChange = (row: NewsCategoryRow) => {
  const next = row.status === 1 ? 0 : 1;
  return changeNewsCategoryStatus({ id: row.id, status: next })
    .then(res => {
      ElMessage.success({ message: res.msg || "状态修改成功" });
      row.status = next;
      return true;
    })
    .catch(() => false);
};

const columns = reactive<ColumnProps<NewsCategoryRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 60 },
  {
    prop: "categoryName",
    label: "分类名称",
    search: { el: "input" }
  },
  {
    prop: "sort",
    label: "排序",
    width: 100
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
    prop: "remark",
    label: "备注",
    minWidth: 180
  },
  {
    prop: "createTime",
    label: "创建时间",
    width: 180
  },
  { prop: "operation", label: "操作", fixed: "right", width: 180 }
]);
</script>
