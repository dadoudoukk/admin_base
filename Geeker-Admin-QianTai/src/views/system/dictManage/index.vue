<template>
  <div class="table-box">
    <ProTable ref="typeTableRef" :columns="typeColumns" :request-api="getDictTypeTableList" :data-callback="dataCallback">
      <template #tableHeader="{ selectedListIds }">
        <el-button v-auth="'dictType:add'" type="primary" :icon="CirclePlus" @click="openTypeAdd">新增字典类型</el-button>
        <el-button
          v-auth="'dictType:delete'"
          type="danger"
          :icon="Delete"
          plain
          :disabled="!selectedListIds?.length"
          @click="batchDeleteType(selectedListIds)"
        >
          批量删除
        </el-button>
      </template>
      <template #operation="scope">
        <el-button type="primary" link :icon="Setting" @click="openDataDrawer(scope.row)">字典配置</el-button>
        <el-button v-auth="'dictType:edit'" type="primary" link :icon="EditPen" @click="openTypeEdit(scope.row)">编辑</el-button>
        <el-button v-auth="'dictType:delete'" type="danger" link :icon="Delete" @click="deleteTypeOne(scope.row)">删除</el-button>
      </template>
    </ProTable>

    <el-dialog
      v-model="typeDialogVisible"
      :title="isTypeEdit ? '编辑字典类型' : '新增字典类型'"
      width="520px"
      destroy-on-close
      @closed="resetTypeForm"
    >
      <el-form ref="typeFormRef" :model="typeForm" :rules="typeRules" label-width="100px">
        <el-form-item label="字典名称" prop="dictName">
          <el-input v-model="typeForm.dictName" placeholder="如：用户性别" clearable />
        </el-form-item>
        <el-form-item label="字典编码" prop="dictCode">
          <el-input v-model="typeForm.dictCode" placeholder="如：sys_user_sex" clearable :disabled="isTypeEdit" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="typeForm.status" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="typeForm.remark" type="textarea" :rows="3" placeholder="选填" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="typeDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitTypeForm">确定</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="dataDrawerVisible"
      :title="drawerTitle"
      size="58%"
      destroy-on-close
      @opened="onDrawerOpened"
      @closed="onDrawerClosed"
    >
      <ProTable
        ref="dataTableRef"
        :columns="dataColumns"
        :request-api="getDictDataTableList"
        :data-callback="dataCallback"
        :request-auto="false"
      >
        <template #tableHeader="{ selectedListIds }">
          <el-button v-auth="'dictData:add'" type="primary" :icon="CirclePlus" @click="openDataAdd">新增字典数据</el-button>
          <el-button
            v-auth="'dictData:delete'"
            type="danger"
            :icon="Delete"
            plain
            :disabled="!selectedListIds?.length"
            @click="batchDeleteData(selectedListIds)"
          >
            批量删除
          </el-button>
        </template>
        <template #operation="scope">
          <el-button v-auth="'dictData:edit'" type="primary" link :icon="EditPen" @click="openDataEdit(scope.row)">
            编辑
          </el-button>
          <el-button v-auth="'dictData:delete'" type="danger" link :icon="Delete" @click="deleteDataOne(scope.row)">
            删除
          </el-button>
        </template>
      </ProTable>
    </el-drawer>

    <el-dialog
      v-model="dataDialogVisible"
      :title="isDataEdit ? '编辑字典数据' : '新增字典数据'"
      width="520px"
      destroy-on-close
      @closed="resetDataForm"
    >
      <el-form ref="dataFormRef" :model="dataForm" :rules="dataRules" label-width="100px">
        <el-form-item label="字典编码" prop="dictCode">
          <el-input v-model="dataForm.dictCode" disabled />
        </el-form-item>
        <el-form-item label="字典标签" prop="dictLabel">
          <el-input v-model="dataForm.dictLabel" placeholder="如：男" clearable />
        </el-form-item>
        <el-form-item label="字典值" prop="dictValue">
          <el-input v-model="dataForm.dictValue" placeholder="如：1" clearable />
        </el-form-item>
        <el-form-item label="排序" prop="sort">
          <el-input-number v-model="dataForm.sort" :min="0" :step="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="dataForm.status" />
        </el-form-item>
        <el-form-item label="备注" prop="remark">
          <el-input v-model="dataForm.remark" type="textarea" :rows="3" placeholder="选填" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dataDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitDataForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="tsx" name="dictManage">
import { computed, nextTick, reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen, Setting } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import {
  addDictData,
  addDictType,
  changeDictDataStatus,
  changeDictTypeStatus,
  deleteDictData,
  deleteDictType,
  editDictData,
  editDictType,
  getDictDataList,
  getDictTypeList,
  type DictDataRow,
  type DictTypeRow
} from "@/api/modules/dict";
import { useHandleData } from "@/hooks/useHandleData";

const typeTableRef = ref<ProTableInstance>();
const typeDialogVisible = ref(false);
const isTypeEdit = ref(false);
const typeFormRef = ref<FormInstance>();
const typeForm = reactive({
  id: "",
  dictName: "",
  dictCode: "",
  status: true,
  remark: ""
});

const dataDrawerVisible = ref(false);
const currentDictCode = ref("");
const currentDictName = ref("");
const drawerTitle = computed(() => `字典配置 — ${currentDictName.value || currentDictCode.value}`);
const dataTableRef = ref<ProTableInstance>();
const dataDialogVisible = ref(false);
const isDataEdit = ref(false);
const dataFormRef = ref<FormInstance>();
const dataForm = reactive({
  id: "",
  dictCode: "",
  dictLabel: "",
  dictValue: "",
  sort: 0,
  status: true,
  remark: ""
});

const typeRules: FormRules = {
  dictName: [{ required: true, message: "请输入字典名称", trigger: "blur" }],
  dictCode: [{ required: true, message: "请输入字典编码", trigger: "blur" }]
};

const dataRules: FormRules = {
  dictLabel: [{ required: true, message: "请输入字典标签", trigger: "blur" }],
  dictValue: [{ required: true, message: "请输入字典值", trigger: "blur" }]
};

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getDictTypeTableList = (params: any) => getDictTypeList(JSON.parse(JSON.stringify(params)));
const getDictDataTableList = (params: any) => {
  if (!currentDictCode.value) {
    return Promise.resolve({ data: { list: [], total: 0, pageNum: 1, pageSize: 10 }, code: 200, msg: "success" });
  }
  return getDictDataList({
    ...JSON.parse(JSON.stringify(params)),
    dictCode: currentDictCode.value
  });
};

const openTypeAdd = () => {
  isTypeEdit.value = false;
  typeDialogVisible.value = true;
};

const openTypeEdit = (row: DictTypeRow) => {
  isTypeEdit.value = true;
  typeForm.id = row.id;
  typeForm.dictName = row.dictName;
  typeForm.dictCode = row.dictCode;
  typeForm.status = row.status === 1;
  typeForm.remark = row.remark || "";
  typeDialogVisible.value = true;
};

const resetTypeForm = () => {
  typeForm.id = "";
  typeForm.dictName = "";
  typeForm.dictCode = "";
  typeForm.status = true;
  typeForm.remark = "";
  isTypeEdit.value = false;
  typeFormRef.value?.clearValidate();
};

const submitTypeForm = () => {
  typeFormRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      if (isTypeEdit.value) {
        const res = await editDictType({
          id: typeForm.id,
          dictName: typeForm.dictName.trim(),
          dictCode: typeForm.dictCode.trim(),
          status: typeForm.status,
          remark: typeForm.remark || undefined
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addDictType({
          dictName: typeForm.dictName.trim(),
          dictCode: typeForm.dictCode.trim(),
          status: typeForm.status,
          remark: typeForm.remark || undefined
        });
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      typeDialogVisible.value = false;
      typeTableRef.value?.getTableList();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const deleteTypeOne = async (row: DictTypeRow) => {
  await useHandleData(deleteDictType, { id: [row.id] }, `删除【${row.dictName}】字典类型`);
  typeTableRef.value?.getTableList();
};

const batchDeleteType = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteDictType, { id: ids }, "删除所选字典类型");
  typeTableRef.value?.clearSelection();
  typeTableRef.value?.getTableList();
};

const openDataDrawer = async (row: DictTypeRow) => {
  currentDictCode.value = row.dictCode;
  currentDictName.value = row.dictName;
  dataDrawerVisible.value = true;
  await nextTick();
  dataTableRef.value?.getTableList();
};

const onDrawerOpened = () => {
  dataTableRef.value?.getTableList();
};

const onDrawerClosed = () => {
  currentDictCode.value = "";
  currentDictName.value = "";
};

const openDataAdd = () => {
  if (!currentDictCode.value) return;
  isDataEdit.value = false;
  dataForm.dictCode = currentDictCode.value;
  dataDialogVisible.value = true;
};

const openDataEdit = (row: DictDataRow) => {
  isDataEdit.value = true;
  dataForm.id = row.id;
  dataForm.dictCode = row.dictCode;
  dataForm.dictLabel = row.dictLabel;
  dataForm.dictValue = row.dictValue;
  dataForm.sort = row.sort ?? 0;
  dataForm.status = !!row.status;
  dataForm.remark = row.remark || "";
  dataDialogVisible.value = true;
};

const resetDataForm = () => {
  dataForm.id = "";
  dataForm.dictCode = currentDictCode.value;
  dataForm.dictLabel = "";
  dataForm.dictValue = "";
  dataForm.sort = 0;
  dataForm.status = true;
  dataForm.remark = "";
  isDataEdit.value = false;
  dataFormRef.value?.clearValidate();
};

const submitDataForm = () => {
  dataFormRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      if (isDataEdit.value) {
        const res = await editDictData({
          id: dataForm.id,
          dictCode: dataForm.dictCode,
          dictLabel: dataForm.dictLabel.trim(),
          dictValue: dataForm.dictValue.trim(),
          sort: dataForm.sort,
          status: dataForm.status,
          remark: dataForm.remark || undefined
        });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addDictData({
          dictCode: dataForm.dictCode,
          dictLabel: dataForm.dictLabel.trim(),
          dictValue: dataForm.dictValue.trim(),
          sort: dataForm.sort,
          status: dataForm.status,
          remark: dataForm.remark || undefined
        });
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      dataDialogVisible.value = false;
      dataTableRef.value?.getTableList();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const deleteDataOne = async (row: DictDataRow) => {
  await useHandleData(deleteDictData, { id: [row.id] }, `删除【${row.dictLabel}】字典数据`);
  dataTableRef.value?.getTableList();
};

const batchDeleteData = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteDictData, { id: ids }, "删除所选字典数据");
  dataTableRef.value?.clearSelection();
  dataTableRef.value?.getTableList();
};

const handleTypeStatusBeforeChange = (row: DictTypeRow) => {
  const next = row.status === 1 ? 0 : 1;
  return changeDictTypeStatus({ id: row.id, status: next })
    .then(res => {
      ElMessage.success({ message: res.msg || "状态修改成功" });
      row.status = next;
      return true;
    })
    .catch(() => false);
};

const handleDataStatusBeforeChange = (row: DictDataRow) => {
  const next = !row.status;
  return changeDictDataStatus({ id: row.id, status: next })
    .then(res => {
      ElMessage.success({ message: res.msg || "状态修改成功" });
      row.status = next;
      return true;
    })
    .catch(() => false);
};

const typeColumns = reactive<ColumnProps<DictTypeRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 60 },
  {
    prop: "dictName",
    label: "字典名称",
    search: { el: "input" }
  },
  {
    prop: "dictCode",
    label: "字典编码",
    minWidth: 180,
    search: { el: "input" }
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
        beforeChange={() => handleTypeStatusBeforeChange(scope.row)}
      />
    )
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

const dataColumns = reactive<ColumnProps<DictDataRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 60 },
  {
    prop: "dictLabel",
    label: "字典标签",
    search: { el: "input" }
  },
  {
    prop: "dictValue",
    label: "字典值",
    width: 120,
    search: { el: "input" }
  },
  {
    prop: "sort",
    label: "排序",
    width: 90
  },
  {
    prop: "status",
    label: "状态",
    width: 100,
    render: scope => <el-switch v-model={scope.row.status} beforeChange={() => handleDataStatusBeforeChange(scope.row)} />
  },
  {
    prop: "remark",
    label: "备注",
    minWidth: 160
  },
  { prop: "operation", label: "操作", fixed: "right", width: 180 }
]);
</script>
