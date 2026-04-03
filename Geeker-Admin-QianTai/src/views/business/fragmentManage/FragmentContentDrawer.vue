<template>
  <el-drawer v-model="visible" :title="drawerTitle" size="min(920px, 96vw)" destroy-on-close @closed="onClosed">
    <div v-if="categoryId" class="table-box drawer-inner">
      <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
        <template #tableHeader="{ selectedListIds }">
          <el-button v-auth="'fragmentContent:add'" type="primary" :icon="CirclePlus" @click="openAdd">新增内容</el-button>
          <el-button
            v-auth="'fragmentContent:delete'"
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
          <el-button v-auth="'fragmentContent:edit'" type="primary" link :icon="EditPen" @click="openEdit(scope.row)">
            编辑
          </el-button>
          <el-button v-auth="'fragmentContent:delete'" type="danger" link :icon="Delete" @click="deleteOne(scope.row)">
            删除
          </el-button>
        </template>
      </ProTable>

      <el-dialog
        v-model="dialogVisible"
        :title="isEdit ? '编辑碎片内容' : '新增碎片内容'"
        width="560px"
        append-to-body
        destroy-on-close
        @closed="resetForm"
      >
        <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
          <el-form-item label="标题" prop="title">
            <el-input v-model="form.title" placeholder="请输入标题" clearable />
          </el-form-item>
          <el-form-item label="图片" prop="imageUrl">
            <UploadImg v-model:image-url="form.imageUrl" :api="uploadImg" height="120px" width="120px" />
          </el-form-item>
          <el-form-item label="跳转链接" prop="linkUrl">
            <el-input v-model="form.linkUrl" placeholder="选填" clearable />
          </el-form-item>
          <el-form-item label="文本内容" prop="content">
            <el-input v-model="form.content" type="textarea" :rows="4" placeholder="选填" clearable />
          </el-form-item>
          <el-form-item label="排序" prop="sort">
            <el-input-number v-model="form.sort" :min="0" :step="1" style="width: 100%" />
          </el-form-item>
          <el-form-item label="状态" prop="status">
            <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="dialogVisible = false">取消</el-button>
          <el-button type="primary" @click="submitForm">确定</el-button>
        </template>
      </el-dialog>
    </div>
  </el-drawer>
</template>

<script setup lang="tsx">
import { computed, reactive, ref, watch } from "vue";
import { CirclePlus, Delete, EditPen } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import UploadImg from "@/components/Upload/Img.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import { uploadImg } from "@/api/modules/upload";
import {
  addFragmentContent,
  changeFragmentContentStatus,
  deleteFragmentContent,
  editFragmentContent,
  getFragmentContentList,
  type FragmentContentRow
} from "@/api/modules/fragment";
import { useHandleData } from "@/hooks/useHandleData";

const props = defineProps<{
  modelValue: boolean;
  categoryId: string;
  categoryCode: string;
  categoryName: string;
}>();

const emit = defineEmits<{ (e: "update:modelValue", v: boolean): void }>();

const visible = computed({
  get: () => props.modelValue,
  set: v => emit("update:modelValue", v)
});

const drawerTitle = computed(() => {
  if (!props.categoryId) return "碎片内容";
  return `碎片内容 — ${props.categoryName}（${props.categoryCode}）`;
});

const proTable = ref<ProTableInstance>();
const dialogVisible = ref(false);
const isEdit = ref(false);
const formRef = ref<FormInstance>();

const form = reactive({
  id: "",
  title: "",
  imageUrl: "",
  linkUrl: "",
  content: "",
  sort: 0,
  status: 1
});

const rules: FormRules = {
  title: [{ required: true, message: "请输入标题", trigger: "blur" }]
};

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => {
  const p = JSON.parse(JSON.stringify(params));
  p.categoryId = props.categoryId;
  return getFragmentContentList(p);
};

watch(
  () => props.modelValue,
  v => {
    if (v && props.categoryId) {
      queueMicrotask(() => proTable.value?.getTableList());
    }
  }
);

const onClosed = () => {
  proTable.value?.clearSelection?.();
};

const openAdd = () => {
  isEdit.value = false;
  dialogVisible.value = true;
};

const openEdit = (row: FragmentContentRow) => {
  isEdit.value = true;
  form.id = row.id;
  form.title = row.title || "";
  form.imageUrl = row.imageUrl || "";
  form.linkUrl = row.linkUrl || "";
  form.content = row.content || "";
  form.sort = Number(row.sort ?? 0);
  form.status = row.status === 1 ? 1 : 0;
  dialogVisible.value = true;
};

const resetForm = () => {
  form.id = "";
  form.title = "";
  form.imageUrl = "";
  form.linkUrl = "";
  form.content = "";
  form.sort = 0;
  form.status = 1;
  isEdit.value = false;
  formRef.value?.clearValidate();
};

const submitForm = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      const payload = {
        title: form.title.trim(),
        imageUrl: form.imageUrl || undefined,
        linkUrl: form.linkUrl || undefined,
        content: form.content || undefined,
        sort: form.sort,
        status: form.status
      };
      if (isEdit.value) {
        const res = await editFragmentContent({ id: form.id, ...payload });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addFragmentContent({ categoryId: props.categoryId, ...payload });
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      dialogVisible.value = false;
      proTable.value?.getTableList();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const deleteOne = async (row: FragmentContentRow) => {
  await useHandleData(deleteFragmentContent, { id: [row.id] }, `删除【${row.title}】`);
  proTable.value?.getTableList();
};

const batchDelete = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteFragmentContent, { id: ids }, "删除所选内容");
  proTable.value?.clearSelection();
  proTable.value?.getTableList();
};

const handleStatusBeforeChange = (row: FragmentContentRow) => {
  const next = row.status === 1 ? 0 : 1;
  return changeFragmentContentStatus({ id: row.id, status: next })
    .then(res => {
      ElMessage.success({ message: res.msg || "状态修改成功" });
      row.status = next;
      return true;
    })
    .catch(() => false);
};

const columns = reactive<ColumnProps<FragmentContentRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 56 },
  {
    prop: "title",
    label: "标题",
    minWidth: 160,
    search: { el: "input" }
  },
  {
    prop: "imageUrl",
    label: "图片",
    width: 88,
    render: scope => {
      const url = scope.row.imageUrl;
      if (!url) return "--";
      return (
        <el-image style="width: 56px; height: 56px" src={url} preview-src-list={[url]} preview-teleported={true} fit="cover" />
      );
    }
  },
  {
    prop: "linkUrl",
    label: "跳转链接",
    minWidth: 140,
    showOverflowTooltip: true
  },
  {
    prop: "content",
    label: "文本",
    minWidth: 120,
    showOverflowTooltip: true
  },
  {
    prop: "sort",
    label: "排序",
    width: 80
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
    width: 170
  },
  { prop: "operation", label: "操作", fixed: "right", width: 160 }
]);
</script>

<style scoped lang="scss">
.drawer-inner {
  padding: 0;
}
</style>
