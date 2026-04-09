<template>
  <div class="table-box">
    <ProTable ref="proTable" :columns="columns" :request-api="getTableList" :data-callback="dataCallback">
      <template #tableHeader>
        <el-button type="primary" :icon="Refresh" :loading="syncLoading" @click="handleSync">一键同步后端接口</el-button>
      </template>
      <template #operation="scope">
        <el-button type="primary" link @click="openConfig(scope.row)">配置</el-button>
      </template>
    </ProTable>

    <el-drawer v-model="drawerVisible" title="接口配置" size="520px" destroy-on-close @closed="resetForm">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="接口路径">
          <el-input v-model="form.apiPath" disabled />
        </el-form-item>
        <el-form-item label="请求方式">
          <el-input v-model="form.apiMethod" disabled />
        </el-form-item>
        <el-form-item label="接口名称" prop="api_name">
          <el-input v-model="form.api_name" placeholder="请输入接口名称" clearable />
        </el-form-item>
        <el-form-item label="所属模块" prop="api_module">
          <el-select
            v-model="form.api_module"
            class="w-full"
            filterable
            clearable
            allow-create
            default-first-option
            placeholder="选择菜单板块或手动输入"
          >
            <el-option v-for="o in moduleOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="限流 QPS" prop="rate_limit">
          <el-input-number v-model="form.rate_limit" :min="0" :step="1" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="3" clearable />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="drawerVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="submitEdit">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="tsx" name="apiManage">
import { onMounted, reactive, ref } from "vue";
import { Refresh } from "@element-plus/icons-vue";
import { ElMessage, type FormInstance, type FormRules } from "element-plus";
import ProTable from "@/components/ProTable/index.vue";
import type { ColumnProps, ProTableInstance } from "@/components/ProTable/interface";
import {
  changeSysApiStatus,
  editSysApi,
  getSysApiList,
  getSysApiModuleOptions,
  syncSysApi,
  type ApiModuleOption,
  type SysApiRow
} from "@/api/modules/sysApi";

const proTable = ref<ProTableInstance>();
const syncLoading = ref(false);
const drawerVisible = ref(false);
const submitLoading = ref(false);
const formRef = ref<FormInstance>();
const moduleOptions = ref<ApiModuleOption[]>([]);

const dataCallback = (data: any) => ({
  list: data.list,
  total: data.total
});

const getTableList = (params: any) => getSysApiList(JSON.parse(JSON.stringify(params)));

const switchLoadingMap = reactive<Record<string, boolean>>({});
const switchKey = (id: string, field: string) => `${id}_${field}`;

const toggleStatus = async (row: SysApiRow, field: "status" | "auth_required" | "log_required", value: boolean) => {
  const key = switchKey(row.id, field);
  if (switchLoadingMap[key]) return;
  switchLoadingMap[key] = true;
  try {
    const res = await changeSysApiStatus({ id: row.id, field, value });
    ElMessage.success({ message: res.msg || "修改成功" });
    if (field === "status") row.status = value ? 1 : 0;
    if (field === "auth_required") row.authRequired = value ? 1 : 0;
    if (field === "log_required") row.logRequired = value ? 1 : 0;
  } finally {
    switchLoadingMap[key] = false;
  }
};

const handleSync = async () => {
  if (syncLoading.value) return;
  syncLoading.value = true;
  try {
    const res = await syncSysApi();
    ElMessage.success({ message: res.msg || "同步成功" });
    proTable.value?.getTableList();
  } finally {
    syncLoading.value = false;
  }
};

const form = reactive({
  id: "",
  apiPath: "",
  apiMethod: "",
  api_name: "",
  api_module: "",
  rate_limit: 0,
  remark: ""
});

const rules: FormRules = {
  api_name: [{ required: true, message: "请输入接口名称", trigger: "blur" }],
  api_module: [{ required: true, message: "请选择或输入所属模块", trigger: "change" }],
  rate_limit: [{ required: true, message: "请输入限流QPS", trigger: "change" }]
};

const openConfig = (row: SysApiRow) => {
  form.id = row.id;
  form.apiPath = row.apiPath;
  form.apiMethod = row.apiMethod;
  form.api_name = row.apiName || "";
  form.api_module = row.apiModule || "";
  form.rate_limit = Number(row.rateLimit || 0);
  form.remark = row.remark || "";
  drawerVisible.value = true;
};

const resetForm = () => {
  form.id = "";
  form.apiPath = "";
  form.apiMethod = "";
  form.api_name = "";
  form.api_module = "";
  form.rate_limit = 0;
  form.remark = "";
  formRef.value?.clearValidate();
};

const submitEdit = () => {
  formRef.value?.validate(async valid => {
    if (!valid) return;
    if (submitLoading.value) return;
    submitLoading.value = true;
    try {
      const res = await editSysApi({
        id: form.id,
        api_name: form.api_name.trim(),
        api_module: form.api_module.trim(),
        rate_limit: Number(form.rate_limit || 0),
        remark: form.remark
      });
      ElMessage.success({ message: res.msg || "保存成功" });
      drawerVisible.value = false;
      proTable.value?.getTableList();
    } finally {
      submitLoading.value = false;
    }
  });
};

const loadModuleFilterOptions = async () => {
  try {
    const res = await getSysApiModuleOptions();
    moduleOptions.value = res.data ?? [];
    const col = columns.find(c => c.prop === "apiModule");
    if (col) {
      col.search = { el: "select", props: { filterable: true, clearable: true } };
      col.enum = moduleOptions.value;
    }
  } catch {
    moduleOptions.value = [{ label: "其他", value: "其他" }];
  }
};

onMounted(() => {
  loadModuleFilterOptions();
});

const methodTagType = (m: string) => {
  const u = (m || "").toUpperCase();
  if (u === "GET") return "success";
  if (u === "POST") return "primary";
  if (u === "PUT") return "warning";
  if (u === "PATCH") return "warning";
  if (u === "DELETE") return "danger";
  return "info";
};

const columns = reactive<ColumnProps<SysApiRow>[]>([
  { type: "index", label: "#", width: 56 },
  {
    prop: "apiPath",
    label: "API 路径",
    minWidth: 250,
    search: { el: "input" },
    showOverflowTooltip: true
  },
  {
    prop: "apiMethod",
    label: "请求方式",
    width: 110,
    search: { el: "select" },
    enum: ["GET", "POST", "PUT", "PATCH", "DELETE"].map(x => ({ label: x, value: x })),
    render: scope => <el-tag type={methodTagType(scope.row.apiMethod)}>{scope.row.apiMethod}</el-tag>
  },
  {
    prop: "apiName",
    label: "接口名称",
    minWidth: 180
  },
  {
    prop: "apiModule",
    label: "所属模块",
    minWidth: 140,
    search: { el: "select", props: { filterable: true, clearable: true } },
    enum: [] as ApiModuleOption[]
  },
  {
    prop: "rateLimit",
    label: "限流QPS",
    width: 100
  },
  {
    prop: "status",
    label: "启用",
    width: 100,
    render: scope => (
      <el-switch
        modelValue={Boolean(scope.row.status)}
        loading={switchLoadingMap[switchKey(scope.row.id, "status")]}
        onChange={(val: boolean) => toggleStatus(scope.row, "status", val)}
      />
    )
  },
  {
    prop: "authRequired",
    label: "鉴权",
    width: 100,
    render: scope => (
      <el-switch
        modelValue={Boolean(scope.row.authRequired)}
        loading={switchLoadingMap[switchKey(scope.row.id, "auth_required")]}
        onChange={(val: boolean) => toggleStatus(scope.row, "auth_required", val)}
      />
    )
  },
  {
    prop: "logRequired",
    label: "日志",
    width: 100,
    render: scope => (
      <el-switch
        modelValue={Boolean(scope.row.logRequired)}
        loading={switchLoadingMap[switchKey(scope.row.id, "log_required")]}
        onChange={(val: boolean) => toggleStatus(scope.row, "log_required", val)}
      />
    )
  },
  { prop: "operation", label: "操作", fixed: "right", width: 100 }
]);
</script>
