<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
      <template #tableHeader="{ selectedListIds }">
        <el-button type="primary" :icon="CirclePlus" @click="openAdd">新增新闻</el-button>
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
      :title="isEdit ? '编辑新闻' : '新增新闻'"
      width="820px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="addForm" :rules="rules" label-width="100px">
        <el-form-item label="所属分类" prop="categoryId">
          <el-select v-model="addForm.categoryId" placeholder="请选择分类" style="width: 100%">
            <el-option v-for="item in categoryOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="新闻标题" prop="title">
          <el-input v-model="addForm.title" placeholder="请输入标题" clearable />
        </el-form-item>
        <el-form-item label="作者" prop="author">
          <el-input v-model="addForm.author" placeholder="选填" clearable />
        </el-form-item>
        <el-form-item label="封面图" prop="imageUrl">
          <UploadImg v-model:image-url="addForm.imageUrl" :api="uploadImg" height="140px" width="140px" />
        </el-form-item>
        <el-form-item label="类型" prop="newsType">
          <el-radio-group v-model="addForm.newsType">
            <el-radio :label="0">图文内容</el-radio>
            <el-radio :label="1">外部跳转</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="addForm.newsType === 0" label="正文内容" prop="content">
          <WangEditor height="400px" v-model:value="addForm.content" />
        </el-form-item>
        <el-form-item v-if="addForm.newsType === 1" label="跳转链接" prop="redirectUrl">
          <el-input v-model="addForm.redirectUrl" placeholder="请输入外部链接" clearable />
        </el-form-item>
        <el-form-item label="置顶" prop="isTop">
          <el-switch v-model="addForm.isTop" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-switch v-model="addForm.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="tsx" name="newsArticle">
import { onMounted, reactive, ref } from "vue";
import { CirclePlus, Delete, EditPen } from "@element-plus/icons-vue";
import { ElMessage, FormInstance } from "element-plus";
import type { FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import UploadImg from "@/components/Upload/Img.vue";
import WangEditor from "@/components/WangEditor/index.vue";
import { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import { uploadImg } from "@/api/modules/upload";
import {
  addNewsArticle,
  changeNewsArticleStatus,
  deleteNewsArticle,
  editNewsArticle,
  getAllNewsCategory,
  getNewsArticleList,
  type NewsArticleRow,
  type NewsCategoryOption
} from "@/api/modules/news";
import { useHandleData } from "@/hooks/useHandleData";

const proTable = ref<ProTableInstance>();
const dialogVisible = ref(false);
const isEdit = ref(false);
const formRef = ref<FormInstance>();
const categoryOptions = ref<NewsCategoryOption[]>([]);

const addForm = reactive({
  id: "",
  categoryId: "",
  title: "",
  author: "",
  newsType: 0,
  content: "",
  redirectUrl: "",
  imageUrl: "",
  isTop: 0,
  status: 1
});

const rules: FormRules = {
  categoryId: [{ required: true, message: "请选择分类", trigger: "change" }],
  title: [{ required: true, message: "请输入标题", trigger: "blur" }]
};

onMounted(async () => {
  const res = await getAllNewsCategory();
  categoryOptions.value = res.data || [];
});

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getNewsArticleList(JSON.parse(JSON.stringify(params)));

const openAdd = () => {
  isEdit.value = false;
  dialogVisible.value = true;
};

const openEdit = (row: NewsArticleRow) => {
  isEdit.value = true;
  addForm.id = row.id;
  addForm.categoryId = String(row.categoryId || "");
  addForm.title = row.title || "";
  addForm.author = row.author || "";
  addForm.newsType = Number(row.newsType || 0);
  addForm.content = row.content || "";
  addForm.redirectUrl = row.redirectUrl || "";
  addForm.imageUrl = row.imageUrl || "";
  addForm.isTop = Number(row.isTop || 0);
  addForm.status = Number(row.status || 0);
  dialogVisible.value = true;
};

const resetForm = () => {
  addForm.id = "";
  addForm.categoryId = "";
  addForm.title = "";
  addForm.author = "";
  addForm.newsType = 0;
  addForm.content = "";
  addForm.redirectUrl = "";
  addForm.imageUrl = "";
  addForm.isTop = 0;
  addForm.status = 1;
  isEdit.value = false;
  formRef.value?.clearValidate();
};

const submitForm = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    try {
      const payload = {
        categoryId: addForm.categoryId,
        title: addForm.title.trim(),
        author: addForm.author || undefined,
        newsType: addForm.newsType,
        content: addForm.newsType === 0 ? addForm.content : "",
        redirectUrl: addForm.newsType === 1 ? addForm.redirectUrl : "",
        imageUrl: addForm.imageUrl || undefined,
        isTop: addForm.isTop,
        status: addForm.status
      };
      if (isEdit.value) {
        const res = await editNewsArticle({ id: addForm.id, ...payload });
        ElMessage.success({ message: res.msg || "编辑成功" });
      } else {
        const res = await addNewsArticle(payload);
        ElMessage.success({ message: res.msg || "新增成功" });
      }
      dialogVisible.value = false;
      proTable.value?.getTableList();
    } catch {
      /* 全局拦截器已提示错误 */
    }
  });
};

const deleteOne = async (row: NewsArticleRow) => {
  await useHandleData(deleteNewsArticle, { id: [row.id] }, `删除【${row.title}】新闻`);
  proTable.value?.getTableList();
};

const batchDelete = async (ids: string[]) => {
  if (!ids?.length) return;
  await useHandleData(deleteNewsArticle, { id: ids }, "删除所选新闻");
  proTable.value?.clearSelection();
  proTable.value?.getTableList();
};

const handleStatusBeforeChange = (row: NewsArticleRow) => {
  const next = row.status === 1 ? 0 : 1;
  return changeNewsArticleStatus({ id: row.id, status: next })
    .then(res => {
      ElMessage.success({ message: res.msg || "状态修改成功" });
      row.status = next;
      return true;
    })
    .catch(() => false);
};

const columns = reactive<ColumnProps<NewsArticleRow>[]>([
  { type: "selection", fixed: "left", width: 50 },
  { type: "index", label: "#", width: 60 },
  {
    prop: "title",
    label: "新闻标题",
    minWidth: 220,
    search: { el: "input" }
  },
  {
    prop: "imageUrl",
    label: "封面",
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
    prop: "categoryId",
    label: "所属分类",
    minWidth: 140,
    enum: () => getAllNewsCategory(),
    fieldNames: { label: "label", value: "value" },
    search: { el: "select" },
    render: scope => scope.row.categoryName || "--"
  },
  {
    prop: "author",
    label: "作者",
    width: 120
  },
  {
    prop: "newsType",
    label: "类型",
    width: 110,
    enum: [
      { label: "图文内容", value: 0 },
      { label: "外部跳转", value: 1 }
    ]
  },
  {
    prop: "isTop",
    label: "置顶",
    width: 100,
    render: scope => <el-tag type={scope.row.isTop === 1 ? "danger" : "info"}>{scope.row.isTop === 1 ? "是" : "否"}</el-tag>
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
  { prop: "operation", label: "操作", fixed: "right", width: 180 }
]);
</script>
